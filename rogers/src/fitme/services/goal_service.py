"""
目标闯关系统服务层

- GoalKnowledgeService：知识层查询（原型库/力量标准/进度速率/安全限值）
- GoalRoadmapService：路线图创建（确定性校验）+ 查询
- PerformanceTestService：力量/身体基线记录与查询

create_roadmap 校验规则（1.3.1）：
1. stages 数量 2-8，stage_index 从 1 连续递增；每关 exit_criteria 1-5 条，expected_weeks 2-16。
2. 力量类指标（bench/squat/deadlift/ohp_kg、pull_ups）跨关单调不减；body_fat_pct / waist_cm 单调不增。
3. 每关每指标增量上限 = progress_rates.monthly_max × (expected_weeks/4.33) × 1.3（容差系数）；
   body_fat_pct 用负向 min 计算；超出即拒绝并回传违规项清单。
4. body_fat_pct 值 ≥ 安全下限（male 8 / female 16，读 goal_safety_limits）。
5. 末关与原型 target_metrics 比对：缺核心指标或偏离超 15% → 不阻断，带 warnings。
6. 指标 key 必须在统一词表内；op 只允许 >= / <=。
"""
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.fitme.models.goal import (
    GoalArchetype,
    GoalMilestone,
    GoalRoadmap,
    GoalSafetyLimit,
    PerformanceTest,
    ProgressRate,
    StrengthStandard,
)
from src.fitme.models.health_metric import HealthMetric
from src.fitme.schemas.goal import (
    DESCENDING_METRICS,
    METRIC_KEYS,
    STRENGTH_METRICS,
    GoalRoadmapCreate,
    GoalRoadmapOut,
    PerformanceTestCreate,
)
from src.fitme.schemas.user import HealthMetricCreate
from src.fitme.services.user_service import UserService
from utils.exceptions import BusinessException, ErrorCode

logger = logging.getLogger("fitcream")

_WEEKS_PER_MONTH = 4.33
_INCREMENT_TOLERANCE = 1.3
_MAX_RATIO_DEVIATION = 0.15

# ratio 指标 -> 对应的绝对 kg 指标（关卡出口用绝对值，比对时换算）
_RATIO_TO_ABS = {
    "bench_ratio": "bench_kg",
    "squat_ratio": "squat_kg",
    "deadlift_ratio": "deadlift_kg",
    "ohp_ratio": "ohp_kg",
}


def _now() -> datetime:
    return datetime.utcnow()


def _today() -> date:
    return date.today()


class GoalKnowledgeService:
    """知识层查询"""

    @staticmethod
    async def get_archetypes(db: AsyncSession, gender: Optional[str]) -> list:
        """原型目录：按 display_order 排序；female_only 原型对 male 用户不返回。"""
        q = select(GoalArchetype).where(GoalArchetype.is_active.is_(True)).order_by(
            GoalArchetype.display_order
        )
        rows = (await db.execute(q)).scalars().all()
        result = []
        for a in rows:
            if gender and gender.lower() in ("male", "m", "男") and a.female_only:
                continue
            result.append(
                {
                    "key": a.key,
                    "name": a.name,
                    "tagline": a.tagline,
                    "description": a.description,
                    "female_only": a.female_only,
                    "target_metrics": a.target_metrics,
                    "training_bias": a.training_bias,
                    "diet_bias": a.diet_bias,
                    "stage_hint": a.stage_hint,
                    "stage_narrative_hint": a.stage_narrative_hint,
                }
            )
        return result

    @staticmethod
    async def get_strength_standards(
        db: AsyncSession, gender: str, bodyweight_kg: Optional[float]
    ) -> list:
        """力量标准表：按体重换算各档 kg 值；无体重则返回原始倍数。"""
        rows = (
            await db.execute(
                select(StrengthStandard).where(StrengthStandard.gender == gender)
            )
        ).scalars().all()
        result = []
        for s in rows:
            kg = float(s.bw_multiplier) * bodyweight_kg if bodyweight_kg else None
            result.append(
                {
                    "lift": s.lift,
                    "level": s.level,
                    "bw_multiplier": float(s.bw_multiplier),
                    "kg": round(kg, 1) if kg is not None else None,
                }
            )
        return result

    @staticmethod
    async def get_progress_rates(db: AsyncSession, experience_level: str) -> list:
        rows = (
            await db.execute(
                select(ProgressRate).where(
                    ProgressRate.experience_level == experience_level
                )
            )
        ).scalars().all()
        return [
            {
                "metric": r.metric,
                "monthly_min": float(r.monthly_min),
                "monthly_max": float(r.monthly_max),
                "unit": r.unit,
            }
            for r in rows
        ]

    @staticmethod
    async def get_safety_limits(db: AsyncSession) -> list:
        rows = (await db.execute(select(GoalSafetyLimit))).scalars().all()
        return [
            {
                "metric": r.metric,
                "gender": r.gender,
                "floor_value": float(r.floor_value) if r.floor_value is not None else None,
                "ceiling_value": float(r.ceiling_value) if r.ceiling_value is not None else None,
                "note": r.note,
            }
            for r in rows
        ]


class GoalRoadmapService:
    """路线图创建与查询"""

    @staticmethod
    async def _latest_tests_map(db: AsyncSession, user_id: UUID) -> Dict[str, PerformanceTest]:
        """每位力量动作的最新一次测试记录（作为关卡增量基准）。"""
        rows = (
            await db.execute(
                select(PerformanceTest)
                .where(PerformanceTest.user_id == user_id)
                .order_by(PerformanceTest.lift, PerformanceTest.tested_at.desc())
            )
        ).scalars().all()
        latest: Dict[str, PerformanceTest] = {}
        for r in rows:
            latest.setdefault(r.lift, r)
        return latest

    @staticmethod
    async def _latest_health_metric(
        db: AsyncSession, user_id: UUID
    ) -> Optional[HealthMetric]:
        return await UserService.get_latest_health_metric(db, user_id)

    @staticmethod
    async def _build_baseline_map(
        db: AsyncSession, user_id: UUID
    ) -> Dict[str, float]:
        """指标 key -> 当前基线值（力量测试 / 身体指标）。"""
        baseline: Dict[str, float] = {}
        tests = await GoalRoadmapService._latest_tests_map(db, user_id)
        for lift, test in tests.items():
            baseline[lift + "_kg"] = float(test.value)
            if lift == "pull_up":
                baseline["pull_ups"] = float(test.value)
        health = await GoalRoadmapService._latest_health_metric(db, user_id)
        if health:
            if health.body_fat_pct is not None:
                baseline["body_fat_pct"] = float(health.body_fat_pct)
            if health.waist_cm is not None:
                baseline["waist_cm"] = float(health.waist_cm)
            if health.weight_kg is not None:
                baseline["bodyweight_kg"] = float(health.weight_kg)
        return baseline

    @staticmethod
    async def _validate_structure(data: GoalRoadmapCreate) -> List[str]:
        """规则 1：stages 数量/序号连续/每关条件数与周数。"""
        errors: List[str] = []
        if not (2 <= len(data.stages) <= 8):
            errors.append("关卡数量须在 2-8 个之间")
        for i, st in enumerate(data.stages, start=1):
            if st.stage_index != i:
                errors.append(f"stage_index 必须从 1 连续递增（第 {i} 关应为 {i}，实际 {st.stage_index}）")
            if not (1 <= len(st.exit_criteria) <= 5):
                errors.append(f"第 {st.stage_index} 关出口条件须 1-5 条（实际 {len(st.exit_criteria)}）")
            if not (2 <= st.expected_weeks <= 16):
                errors.append(f"第 {st.stage_index} 关 expected_weeks 须 2-16（实际 {st.expected_weeks}）")
            for c in st.exit_criteria:
                if c.metric not in METRIC_KEYS:
                    errors.append(f"第 {st.stage_index} 关指标「{c.metric}」不在统一词表内")
                if c.op not in (">=", "<="):
                    errors.append(f"第 {st.stage_index} 关指标「{c.metric}」op 只允许 >= / <=")
        return errors

    @staticmethod
    def _check_monotonicity(data: GoalRoadmapCreate) -> List[str]:
        """规则 2：力量类单调不减、降向类单调不增（同类指标跨关出现时）。"""
        errors: List[str] = []
        prev: Dict[str, float] = {}
        for st in data.stages:
            for c in st.exit_criteria:
                if c.metric in STRENGTH_METRICS and c.metric in prev:
                    if c.value < prev[c.metric] - 1e-6:
                        errors.append(
                            f"力量指标「{c.metric}」第 {st.stage_index} 关（{c.value}）不得低于上一关（{prev[c.metric]}）"
                        )
                if c.metric in DESCENDING_METRICS and c.metric in prev:
                    if c.value > prev[c.metric] + 1e-6:
                        errors.append(
                            f"降向指标「{c.metric}」第 {st.stage_index} 关（{c.value}）不得高于上一关（{prev[c.metric]}）"
                        )
                if c.metric in STRENGTH_METRICS or c.metric in DESCENDING_METRICS:
                    prev[c.metric] = c.value
        return errors

    @staticmethod
    async def _check_increments(
        db: AsyncSession,
        data: GoalRoadmapCreate,
        user_id: UUID,
        experience_level: str,
    ) -> List[str]:
        """规则 3：每关每指标增量上限 = 月速率 × (周数/4.33) × 1.3。"""
        errors: List[str] = []
        rate_rows = (
            await db.execute(
                select(ProgressRate).where(
                    ProgressRate.experience_level == experience_level
                )
            )
        ).scalars().all()
        rates: Dict[str, ProgressRate] = {r.metric: r for r in rate_rows}
        baseline = await GoalRoadmapService._build_baseline_map(db, user_id)

        prev_exit: Dict[str, float] = {}
        for st in data.stages:
            for c in st.exit_criteria:
                ref = prev_exit.get(c.metric)
                if ref is None:
                    ref = baseline.get(c.metric)
                if ref is None:
                    continue  # 无基准（无力量训练史/身体指标），跳过增量校验
                inc = c.value - ref
                rate = rates.get(c.metric)
                if rate is None:
                    # bodyweight_kg 用 bodyweight_pct 折算（%体重/月 → kg/月）
                    if c.metric == "bodyweight_kg" and "bodyweight_pct" in rates:
                        r = rates["bodyweight_pct"]
                        limit_up = (
                            float(r.monthly_max) * ref / 100 * st.expected_weeks
                            / _WEEKS_PER_MONTH * _INCREMENT_TOLERANCE
                        )
                        limit_down = (
                            float(r.monthly_min) * ref / 100 * st.expected_weeks
                            / _WEEKS_PER_MONTH * _INCREMENT_TOLERANCE
                        )
                        if inc > limit_up or inc < limit_down:
                            errors.append(
                                f"第 {st.stage_index} 关「{c.metric}」增量 {round(inc,1)}kg 超出可持续范围"
                                f"（{round(limit_down,1)} ~ {round(limit_up,1)}kg）"
                            )
                    continue
                if c.metric in DESCENDING_METRICS:
                    limit = (
                        float(rate.monthly_min) * st.expected_weeks
                        / _WEEKS_PER_MONTH * _INCREMENT_TOLERANCE
                    )
                    if inc < limit:
                        errors.append(
                            f"第 {st.stage_index} 关「{c.metric}」降幅 {round(abs(inc),1)} 超出可持续上限"
                            f"（{round(abs(limit),1)} {rate.unit}）"
                        )
                else:
                    limit = (
                        float(rate.monthly_max) * st.expected_weeks
                        / _WEEKS_PER_MONTH * _INCREMENT_TOLERANCE
                    )
                    if inc > limit:
                        errors.append(
                            f"第 {st.stage_index} 关「{c.metric}」增量 {round(inc,1)} 超出可持续上限"
                            f"（{round(limit,1)} {rate.unit}）"
                        )
                if c.metric in STRENGTH_METRICS or c.metric in DESCENDING_METRICS:
                    prev_exit[c.metric] = c.value
        return errors

    @staticmethod
    async def _check_safety(
        db: AsyncSession, data: GoalRoadmapCreate, gender: str
    ) -> List[str]:
        """规则 4：body_fat_pct 值 ≥ 安全下限（male 8 / female 16）。"""
        errors: List[str] = []
        limits = (
            await db.execute(
                select(GoalSafetyLimit).where(GoalSafetyLimit.metric == "body_fat_pct")
            )
        ).scalars().all()
        floor_map = {
            lim.gender: float(lim.floor_value)
            for lim in limits
            if lim.floor_value is not None
        }
        floor = floor_map.get(gender) or floor_map.get("male")
        if floor is None:
            return errors
        for st in data.stages:
            for c in st.exit_criteria:
                if c.metric == "body_fat_pct" and c.value < floor:
                    errors.append(
                        f"第 {st.stage_index} 关 body_fat_pct={c.value}% 低于健康下限（{floor}%）"
                    )
        return errors

    @staticmethod
    async def _check_final_target(
        db: AsyncSession,
        data: GoalRoadmapCreate,
        gender: str,
        user_id: UUID,
    ) -> List[str]:
        """规则 5：末关与原型 target_metrics 比对 → warnings（不阻断）。"""
        warnings: List[str] = []
        arch = (
            await db.execute(
                select(GoalArchetype).where(GoalArchetype.key == data.archetype_key)
            )
        ).scalar_one_or_none()
        if arch is None:
            warnings.append(f"原型「{data.archetype_key}」不在知识库中，跳过末关比对")
            return warnings
        targets = (arch.target_metrics or {}).get(gender, [])
        if not targets:
            return warnings

        last = data.stages[-1]
        exit_map = {c.metric: c.value for c in last.exit_criteria}
        health = await GoalRoadmapService._latest_health_metric(db, user_id)
        bodyweight = (
            float(health.weight_kg)
            if health and health.weight_kg is not None
            else exit_map.get("bodyweight_kg")
        )

        for t in targets:
            metric = t.get("metric")
            tmin = t.get("min")
            tmax = t.get("max")
            if metric in _RATIO_TO_ABS:
                abs_metric = _RATIO_TO_ABS[metric]
                value = exit_map.get(abs_metric)
                if value is None:
                    warnings.append(f"末关缺少核心指标「{abs_metric}」（对应原型 {metric}）")
                    continue
                if not bodyweight:
                    continue
                value = value / bodyweight
            else:
                value = exit_map.get(metric)
                if value is None:
                    warnings.append(f"末关缺少核心指标「{metric}」（原型目标）")
                    continue

            low = tmin if tmin is not None else None
            high = tmax if tmax is not None else None
            if low is not None and value < low * (1 - _MAX_RATIO_DEVIATION):
                warnings.append(
                    f"末关「{metric}」={round(value,2)} 低于原型目标下限 {low} 超过 15%"
                )
            elif high is not None and value > high * (1 + _MAX_RATIO_DEVIATION):
                warnings.append(
                    f"末关「{metric}」={round(value,2)} 高于原型目标上限 {high} 超过 15%"
                )
        return warnings

    @staticmethod
    async def create_roadmap(
        db: AsyncSession,
        user_id: UUID,
        data: GoalRoadmapCreate,
        gender: Optional[str] = None,
        experience_level: str = "beginner",
    ) -> GoalRoadmap:
        """创建路线图：确定性校验 → 已有 active 置 archived → 建 roadmap + milestones。"""
        errors: List[str] = []
        errors += await GoalRoadmapService._validate_structure(data)
        errors += GoalRoadmapService._check_monotonicity(data)
        errors += await GoalRoadmapService._check_increments(
            db, data, user_id, experience_level
        )
        errors += await GoalRoadmapService._check_safety(db, data, gender or "both")
        if errors:
            raise BusinessException(
                ErrorCode.BAD_REQUEST,
                "路线图校验未通过，请修正后重试：\n- " + "\n- ".join(errors),
            )

        # 整体替换语义：已有 active 路线图先置 archived
        active = (
            await db.execute(
                select(GoalRoadmap).where(
                    GoalRoadmap.user_id == user_id,
                    GoalRoadmap.status == "active",
                )
            )
        ).scalar_one_or_none()
        if active:
            active.status = "archived"
            await db.flush()

        roadmap = GoalRoadmap(
            user_id=user_id,
            archetype_key=data.archetype_key,
            title=data.title,
            description=data.description,
            target_metrics=[m.model_dump() for m in data.target_metrics],
            horizon_months=data.horizon_months,
            status="active",
        )
        db.add(roadmap)
        await db.flush()

        for i, st in enumerate(data.stages):
            db.add(
                GoalMilestone(
                    roadmap_id=roadmap.id,
                    stage_index=st.stage_index,
                    title=st.title,
                    description=st.description,
                    exit_criteria=[c.model_dump() for c in st.exit_criteria],
                    expected_weeks=st.expected_weeks,
                    training_focus=st.training_focus,
                    status="active" if i == 0 else "locked",
                )
            )
        await db.flush()
        await db.refresh(roadmap)

        warnings = await GoalRoadmapService._check_final_target(
            db, data, gender or "both", user_id
        )
        if warnings:
            roadmap_warnings = getattr(roadmap, "_warnings", None)
            if roadmap_warnings is None:
                roadmap._warnings = warnings  # type: ignore[attr-defined]
        return roadmap

    @staticmethod
    async def get_active_roadmap(
        db: AsyncSession, user_id: UUID
    ) -> Optional[GoalRoadmap]:
        row = (
            await db.execute(
                select(GoalRoadmap)
                .where(
                    GoalRoadmap.user_id == user_id,
                    GoalRoadmap.status == "active",
                )
                .order_by(GoalRoadmap.created_at.desc())
            )
        ).scalar_one_or_none()
        return row

    @staticmethod
    async def get_current_milestone(
        db: AsyncSession, user_id: UUID
    ) -> Optional[GoalMilestone]:
        roadmap = await GoalRoadmapService.get_active_roadmap(db, user_id)
        if not roadmap:
            return None
        for m in roadmap.milestones:
            if m.status == "active":
                return m
        return None

    @staticmethod
    async def _current_metric_values(db: AsyncSession, user_id: UUID) -> Dict[str, float]:
        """指标 key -> 当前测量值（力量测试 / 身体指标 / ratio 派生）。"""
        values: Dict[str, float] = {}
        tests = await GoalRoadmapService._latest_tests_map(db, user_id)
        for lift, test in tests.items():
            values[lift + "_kg"] = float(test.value)
            if lift == "pull_up":
                values["pull_ups"] = float(test.value)
        health = await GoalRoadmapService._latest_health_metric(db, user_id)
        if health:
            if health.body_fat_pct is not None:
                values["body_fat_pct"] = float(health.body_fat_pct)
            if health.waist_cm is not None:
                values["waist_cm"] = float(health.waist_cm)
            if health.weight_kg is not None:
                values["bodyweight_kg"] = float(health.weight_kg)
        bw = values.get("bodyweight_kg")
        if bw:
            for ratio, abs_metric in _RATIO_TO_ABS.items():
                if abs_metric in values:
                    values[ratio] = values[abs_metric] / bw
        return values

    @staticmethod
    async def evaluate_current_milestone(
        db: AsyncSession, user_id: UUID
    ) -> dict:
        """复测出关判定：比对当前关出口条件与最新测量值。

        全部达标 → 当前关置 achieved，解锁下一关（第一个 locked 置 active），
        返回 achieved=True；否则返回逐条未达标明细（不落库变更）。
        无 active 路线图或无进行中关卡时返回 evaluated=False。
        """
        roadmap = await GoalRoadmapService.get_active_roadmap(db, user_id)
        if not roadmap:
            return {
                "has_roadmap": False,
                "evaluated": False,
                "message": "当前没有活跃闯关路线图",
            }
        current = next(
            (m for m in roadmap.milestones if m.status == "active"), None
        )
        if current is None:
            return {
                "has_roadmap": True,
                "evaluated": False,
                "message": "当前没有进行中的关卡",
            }

        values = await GoalRoadmapService._current_metric_values(db, user_id)
        criteria: List[dict] = []
        all_met = True
        for c in current.exit_criteria or []:
            metric = c.get("metric")
            op = c.get("op")
            target = c.get("value")
            unit = c.get("unit")
            val = values.get(metric)
            met = False
            reason = None
            if val is None:
                all_met = False
                reason = "缺少测量数据"
            else:
                met = (val >= target) if op == ">=" else (val <= target)
                if not met:
                    all_met = False
            criteria.append(
                {
                    "metric": metric,
                    "op": op,
                    "target": target,
                    "unit": unit,
                    "current": round(val, 2) if val is not None else None,
                    "met": met,
                    "reason": reason,
                }
            )

        if all_met:
            current.status = "achieved"
            current.achieved_at = _now()
            next_milestone = None
            remaining = [m for m in roadmap.milestones if m.status == "locked"]
            if remaining:
                next_milestone = min(remaining, key=lambda m: m.stage_index)
                next_milestone.status = "active"
            await db.flush()
            await db.refresh(current)
            return {
                "has_roadmap": True,
                "evaluated": True,
                "achieved": True,
                "milestone": {
                    "id": str(current.id),
                    "stage_index": current.stage_index,
                    "title": current.title,
                },
                "criteria": criteria,
                "next_milestone": (
                    {
                        "id": str(next_milestone.id),
                        "stage_index": next_milestone.stage_index,
                        "title": next_milestone.title,
                        "training_focus": next_milestone.training_focus,
                    }
                    if next_milestone
                    else None
                ),
                "message": f"「{current.title}」出口条件全部达成，已通关！"
                + (
                    f"下一关「{next_milestone.title}」已解锁。"
                    if next_milestone
                    else "路线图全部通关！"
                ),
            }

        return {
            "has_roadmap": True,
            "evaluated": True,
            "achieved": False,
            "milestone": {
                "id": str(current.id),
                "stage_index": current.stage_index,
                "title": current.title,
            },
            "criteria": criteria,
            "message": f"「{current.title}」尚未达到出关条件，继续加油。",
        }


class PerformanceTestService:
    """力量/身体基线记录与查询"""

    @staticmethod
    async def record_tests(
        db: AsyncSession,
        user_id: UUID,
        lifts: List[PerformanceTestCreate],
        body_metrics: Optional[dict] = None,
    ) -> dict:
        """写 performance_tests 行 + 身体指标写 HealthMetric。

        30 天内同一动作已有测试记录时不重复录入（幂等），返回 skipped 清单。
        """
        body_metrics = body_metrics or {}
        tested_at = body_metrics.get("measure_date") or _today()
        bodyweight_kg = body_metrics.get("weight_kg")
        if bodyweight_kg is None:
            latest = await UserService.get_latest_health_metric(db, user_id)
            bodyweight_kg = float(latest.weight_kg) if latest and latest.weight_kg is not None else None

        cutoff = _today() - timedelta(days=30)
        recorded: List[str] = []
        skipped: List[str] = []
        for lift in lifts:
            dup = (
                await db.execute(
                    select(PerformanceTest.id).where(
                        PerformanceTest.user_id == user_id,
                        PerformanceTest.lift == lift.lift,
                        PerformanceTest.tested_at >= cutoff,
                    )
                )
            ).first()
            if dup:
                skipped.append(lift.lift)
                continue
            db.add(
                PerformanceTest(
                    user_id=user_id,
                    lift=lift.lift,
                    test_type=lift.test_type,
                    value=lift.value,
                    bodyweight_kg=bodyweight_kg,
                    tested_at=lift.tested_at or tested_at,
                    source="chat",
                    note=lift.note,
                )
            )
            recorded.append(lift.lift)

        # 身体指标（体脂/腰围等）写 HealthMetric
        hm_fields = {k: v for k, v in body_metrics.items() if k != "measure_date"}
        if any(v is not None for v in hm_fields.values()):
            await UserService.create_health_metric(
                db,
                user_id,
                HealthMetricCreate(
                    measure_date=tested_at,
                    height_cm=body_metrics.get("height_cm"),
                    weight_kg=body_metrics.get("weight_kg"),
                    body_fat_pct=body_metrics.get("body_fat_pct"),
                    waist_cm=body_metrics.get("waist_cm"),
                    note=body_metrics.get("note"),
                ),
            )
        await db.flush()
        return {"recorded": recorded, "skipped": skipped}

    @staticmethod
    async def get_latest_tests(db: AsyncSession, user_id: UUID) -> dict:
        rows = (
            await db.execute(
                select(PerformanceTest)
                .where(PerformanceTest.user_id == user_id)
                .order_by(PerformanceTest.lift, PerformanceTest.tested_at.desc())
            )
        ).scalars().all()
        latest: dict = {}
        for r in rows:
            latest.setdefault(
                r.lift,
                {
                    "lift": r.lift,
                    "test_type": r.test_type,
                    "value": float(r.value),
                    "bodyweight_kg": float(r.bodyweight_kg) if r.bodyweight_kg is not None else None,
                    "tested_at": r.tested_at.isoformat(),
                    "source": r.source,
                    "note": r.note,
                },
            )
        return latest


def roadmap_to_dict(roadmap: GoalRoadmap, include_warnings: bool = False) -> dict:
    """GoalRoadmap → 可序列化 dict（含 milestones）。"""
    data = GoalRoadmapOut.model_validate(roadmap).model_dump(mode="json")
    if include_warnings:
        warnings = getattr(roadmap, "_warnings", None)
        if warnings:
            data["warnings"] = warnings
    return data
