"""
目标闯关系统离线单测（不连 PostgreSQL，用 FakeDB 桩执行接口）。

覆盖：
- create_roadmap 确定性校验逐条：结构（规则1）/ 词表与 op（规则6）/ 单调性（规则2）/
  增量速率上限（规则3）/ 体脂安全下限（规则4）/ 末关目标比对 warning（规则5）
- seed loader：原型按 (key,gender) upsert、其余表仅空表插入
- create_plan_tool milestone_id 透传（mock db 与 PlanService）
"""
import os
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

import pytest

import app.models  # noqa: F401  (注册全部 ORM mapper，避免关系字符串解析失败)

from src.fitme.models.goal import (
    GoalArchetype,
    GoalSafetyLimit,
    PerformanceTest,
    ProgressRate,
    StrengthStandard,
)
from src.fitme.models.health_metric import HealthMetric
from src.fitme.schemas.goal import GoalRoadmapCreate, MetricCriterion, StageDesign
from src.fitme.services.goal_service import GoalRoadmapService
from utils.exceptions import BusinessException


class _FakeScalarResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class _FakeSingleResult:
    def __init__(self, row):
        self._row = row

    def scalar_one_or_none(self):
        return self._row

    def first(self):
        return self._row


class FakeDB:
    """按 str(select) 表名分发的数据库桩。"""

    def __init__(
        self,
        *,
        rates=None,
        safety=None,
        tests=None,
        health=None,
        archetype=None,
        active_roadmaps=None,
        standards=None,
        progress=None,
    ):
        self.rates = rates or []
        self.safety = safety or []
        self.tests = tests or []
        self.health = health
        self.archetype = archetype
        self.active_roadmaps = active_roadmaps or []
        self.standards = standards or []
        self.progress = progress or []
        self.added = []
        self.upserts = []

    async def execute(self, query):
        q = str(query)
        if "ON CONFLICT" in q and "goal_archetypes" in q:
            self.upserts.append(q)
            return _FakeScalarResult([])
        if "goal_roadmaps" in q:
            return _FakeScalarResult(self.active_roadmaps)
        if "progress_rates" in q:
            return _FakeScalarResult(self.rates or self.progress)
        if "goal_safety_limits" in q:
            return _FakeScalarResult(self.safety)
        if "performance_tests" in q:
            return _FakeScalarResult(self.tests)
        if "health_metrics" in q:
            return _FakeSingleResult(self.health)
        if "goal_archetypes" in q:
            return _FakeScalarResult([self.archetype] if self.archetype is not None else [])
        if "strength_standards" in q:
            return _FakeScalarResult(self.standards)
        raise AssertionError(f"Unexpected query: {q}")

    def add(self, obj):
        self.added.append(obj)

    def add_all(self, objs):
        self.added.extend(objs)

    async def flush(self):
        pass

    async def refresh(self, obj):
        pass


def _c(metric, value, op=">="):
    return MetricCriterion(metric=metric, op=op, value=value)


def _stage(idx, criteria, weeks=8, title=None):
    return StageDesign(
        stage_index=idx,
        title=title or f"第{idx}关",
        exit_criteria=criteria,
        expected_weeks=weeks,
    )


def _roadmap(stages, **kw):
    data = dict(
        archetype_key="lean_aesthetic",
        title="薄肌闯关",
        target_metrics=[],
        stages=stages,
    )
    data.update(kw)
    return GoalRoadmapCreate(**data)


def _beginner_db(**kw):
    """默认 beginner 速率 + 体脂安全下限 + bench 基线 60kg。"""
    defaults = dict(
        rates=[
            ProgressRate(experience_level="beginner", metric="bench_kg", monthly_min=4, monthly_max=8, unit="kg/月"),
            ProgressRate(experience_level="beginner", metric="body_fat_pct", monthly_min=-2.0, monthly_max=-1.0, unit="%/月"),
        ],
        safety=[GoalSafetyLimit(metric="body_fat_pct", gender="male", floor_value=8, ceiling_value=None, note="体脂下限")],
        tests=[PerformanceTest(lift="bench", value=60, tested_at=date(2026, 8, 1), bodyweight_kg=70)],
        health=HealthMetric(user_id=uuid4(), measure_date=date(2026, 8, 1), body_fat_pct=20, weight_kg=70),
        archetype=GoalArchetype(
            key="lean_aesthetic",
            gender="male",
            name="薄肌",
            target_metrics=[
                {"metric": "bench_ratio", "min": 0.9, "max": 1.1, "core": True},
                {"metric": "body_fat_pct", "min": 10, "max": 14, "core": True},
                {"metric": "visceral_fat_level", "max": 5, "core": False},
            ],
        ),
    )
    defaults.update(kw)
    return FakeDB(**defaults)


class TestStructure:
    async def test_out_of_range_stage_count(self):
        # 关卡数 2-8 由 GoalRoadmapCreate schema 强制（min_length=2 / max_length=8）
        with pytest.raises(Exception):
            _roadmap([_stage(1, [_c("bench_kg", 65)])])
        with pytest.raises(Exception):
            _roadmap([_stage(i, [_c("bench_kg", 65 + i)]) for i in range(1, 10)])

    async def test_stage_index_not_continuous(self):
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [_stage(1, [_c("bench_kg", 65)]), _stage(3, [_c("bench_kg", 70)])]
                ),
                gender="male",
            )
        assert "连续递增" in str(ei.value.message)

    async def test_bad_weeks(self):
        # expected_weeks 2-16 由 StageDesign schema 强制（ge=2 / le=16）
        with pytest.raises(Exception):
            _stage(1, [_c("bench_kg", 65)], weeks=1)
        with pytest.raises(Exception):
            _stage(1, [_c("bench_kg", 65)], weeks=17)


class TestVocabulary:
    async def test_invalid_metric_key(self):
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [_stage(1, [_c("nonexistent_metric", 65)]), _stage(2, [_c("bench_kg", 70)])]
                ),
                gender="male",
            )
        assert "统一词表" in str(ei.value.message)

    async def test_invalid_op(self):
        # op 只允许 >= / <=，由 MetricCriterion schema 强制
        with pytest.raises(Exception):
            MetricCriterion(metric="bench_kg", op="==", value=65)


class TestMonotonicity:
    async def test_strength_decrease_rejected(self):
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [_stage(1, [_c("bench_kg", 70)]), _stage(2, [_c("bench_kg", 65)])]
                ),
                gender="male",
            )
        assert "不得低于" in str(ei.value.message)

    async def test_body_fat_increase_rejected(self):
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [
                        _stage(1, [_c("body_fat_pct", 16, op="<=")]),
                        _stage(2, [_c("body_fat_pct", 18, op="<=")]),
                    ]
                ),
                gender="male",
            )
        assert "不得高于" in str(ei.value.message)


class TestIncrement:
    async def test_bench_increment_over_limit_rejected(self):
        # 8 周上限 = 8×(8/4.33)×1.3 ≈ 19.2kg；基线 60 -> 85 增量 25 超限
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [_stage(1, [_c("bench_kg", 85)]), _stage(2, [_c("bench_kg", 90)], weeks=4)]
                ),
                gender="male",
            )
        assert "超出可持续上限" in str(ei.value.message)

    async def test_bench_increment_within_limit_ok(self):
        db = _beginner_db()
        roadmap = await GoalRoadmapService.create_roadmap(
            db,
            uuid4(),
            _roadmap(
                [_stage(1, [_c("bench_kg", 65)]), _stage(2, [_c("bench_kg", 75)], weeks=12)]
            ),
            gender="male",
        )
        assert roadmap is not None

    async def test_body_fat_decrease_over_limit_rejected(self):
        # 8 周下限 = -2×(8/4.33)×1.3 ≈ -4.8；基线 20 -> 12 降 8 超限
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [
                        _stage(1, [_c("body_fat_pct", 12, op="<=")]),
                        _stage(2, [_c("body_fat_pct", 11, op="<=")], weeks=4),
                    ]
                ),
                gender="male",
            )
        assert "超出可持续上限" in str(ei.value.message)


class TestSafety:
    async def test_body_fat_below_floor_rejected(self):
        db = _beginner_db()
        with pytest.raises(BusinessException) as ei:
            await GoalRoadmapService.create_roadmap(
                db,
                uuid4(),
                _roadmap(
                    [
                        _stage(1, [_c("body_fat_pct", 7, op="<=")]),
                        _stage(2, [_c("body_fat_pct", 9, op="<=")], weeks=4),
                    ]
                ),
                gender="male",
            )
        assert "健康下限" in str(ei.value.message)


class TestFinalTargetWarning:
    async def test_missing_core_metric_warns(self):
        db = _beginner_db()
        roadmap = await GoalRoadmapService.create_roadmap(
            db,
            uuid4(),
            _roadmap(
                [
                    _stage(1, [_c("bench_kg", 65)]),
                    _stage(2, [_c("bench_kg", 75), _c("waist_cm", 78, op="<=")], weeks=12),
                ]
            ),
            gender="male",
        )
        warnings = getattr(roadmap, "_warnings", None)
        assert warnings, "末关缺少原型核心指标应产生 warning"
        assert any("body_fat_pct" in w for w in warnings)

    async def test_within_target_no_warning(self):
        db = _beginner_db()
        roadmap = await GoalRoadmapService.create_roadmap(
            db,
            uuid4(),
            _roadmap(
                [
                    _stage(1, [_c("bench_kg", 65)]),
                    _stage(
                        2,
                        [_c("bench_kg", 75), _c("body_fat_pct", 14, op="<=")],
                        weeks=12,
                    ),
                ]
            ),
            gender="male",
        )
        warnings = getattr(roadmap, "_warnings", None) or []
        assert not any("缺少核心指标" in w for w in warnings)
        # display-only（core=false）指标不参与末关比对，不应产生 warning
        assert not any("visceral_fat_level" in w for w in warnings)


class TestSeedIdempotency:
    async def test_archetypes_upserted_others_skipped_when_nonempty(self):
        db = FakeDB(
            archetype=object(),
            standards=[object()],
            progress=[object()],
            safety=[object()],
        )
        from src.fitme.services.goal_knowledge_seed import seed_goal_knowledge

        await seed_goal_knowledge(db)
        # v2：原型每次启动按 (key,gender) upsert（种子为唯一真源），其余表非空跳过
        assert len(db.upserts) == 11
        assert db.added == [], "非空表不应再 ORM 插入标准/速率/安全限值"

    async def test_inserts_when_empty(self):
        db = FakeDB()
        from src.fitme.services.goal_knowledge_seed import seed_goal_knowledge

        await seed_goal_knowledge(db)
        # 11 原型 upsert + 40 力量标准 + 18 速率 + 4 安全限值
        standard_rows = [o for o in db.added if isinstance(o, StrengthStandard)]
        rate_rows = [o for o in db.added if isinstance(o, ProgressRate)]
        limit_rows = [o for o in db.added if isinstance(o, GoalSafetyLimit)]
        assert len(db.upserts) == 11
        assert len(standard_rows) == 40
        assert len(rate_rows) == 18
        assert len(limit_rows) == 4


class TestCreatePlanMilestoneId:
    async def test_milestone_id_passthrough(self, monkeypatch):
        from contextlib import asynccontextmanager

        from src.fitme.schemas.plan import PlanDayCreate
        from src.agents.harness.tools.plan import plan_tools

        captured = {}

        @asynccontextmanager
        async def _scope():
            yield object()

        async def fake_create_plan(db, user_id, data):
            captured["milestone_id"] = data.milestone_id
            return SimpleNamespace(
                id="plan-1", name="p", goal="gain_muscle", difficulty="beginner",
                weeks=4, status="active", days=[],
            )

        async def fake_get_plan_detail(db, pid, user_id):
            return SimpleNamespace(
                id="plan-1", name="p", goal="gain_muscle", difficulty="beginner",
                weeks=4, status="active", days=[],
            )

        monkeypatch.setattr(plan_tools, "session_scope", _scope)
        monkeypatch.setattr(plan_tools.PlanService, "create_plan", fake_create_plan)
        monkeypatch.setattr(plan_tools.PlanService, "get_plan_detail", fake_get_plan_detail)

        mid = "11111111-1111-1111-1111-111111111111"
        result = await plan_tools.create_plan_tool.coroutine(
            goal="gain_muscle",
            days_per_week=4,
            difficulty="beginner",
            name="p",
            weeks=4,
            days=[PlanDayCreate(day_of_week=1, focus="x")],
            milestone_id=mid,
            config={"configurable": {"user_id": "22222222-2222-2222-2222-222222222222"}},
        )
        assert result["success"] is True
        assert captured["milestone_id"] == UUID(mid)

    async def test_no_milestone_id_none(self, monkeypatch):
        from contextlib import asynccontextmanager

        from src.fitme.schemas.plan import PlanDayCreate
        from src.agents.harness.tools.plan import plan_tools

        captured = {}

        @asynccontextmanager
        async def _scope():
            yield object()

        async def fake_create_plan(db, user_id, data):
            captured["milestone_id"] = data.milestone_id
            return SimpleNamespace(
                id="plan-1", name="p", goal="gain_muscle", difficulty="beginner",
                weeks=4, status="active", days=[],
            )

        async def fake_get_plan_detail(db, pid, user_id):
            return SimpleNamespace(
                id="plan-1", name="p", goal="gain_muscle", difficulty="beginner",
                weeks=4, status="active", days=[],
            )

        monkeypatch.setattr(plan_tools, "session_scope", _scope)
        monkeypatch.setattr(plan_tools.PlanService, "create_plan", fake_create_plan)
        monkeypatch.setattr(plan_tools.PlanService, "get_plan_detail", fake_get_plan_detail)

        result = await plan_tools.create_plan_tool.coroutine(
            goal="gain_muscle",
            days_per_week=4,
            difficulty="beginner",
            name="p",
            weeks=4,
            days=[PlanDayCreate(day_of_week=1, focus="x")],
            config={"configurable": {"user_id": "22222222-2222-2222-2222-222222222222"}},
        )
        assert result["success"] is True
        assert captured["milestone_id"] is None
