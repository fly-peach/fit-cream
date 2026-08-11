"""
用户服务

提供用户查询和资料更新的业务逻辑。
支持部分更新（仅修改传入的字段）。
"""
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.fitme.models.health_metric import HealthMetric
from src.fitme.models.user import User
from src.fitme.models.user_goals import UserGoals
from src.fitme.models.user_settings import UserSettings
from src.fitme.schemas.user import (
    HealthMetricCreate,
    HealthMetricUpdate,
    UserGoalsUpdate,
    UserUpdate,
)
from utils.exceptions import NotFoundException


def compute_bmi(
    height_cm: Optional[float], weight_kg: Optional[float]
) -> tuple[Optional[float], Optional[str]]:
    """由身高(cm)/体重(kg)派生 BMI 与其分类（单一来源，避免各分支阈值发散）。

    返回 (bmi, status)；参数任一缺失返回 (None, None)。
    """
    if not height_cm or not weight_kg:
        return None, None
    bmi = float(weight_kg) / ((float(height_cm) / 100) ** 2)
    status = (
        "偏瘦" if bmi < 18.5
        else "正常" if bmi < 24
        else "偏胖" if bmi < 28
        else "肥胖"
    )
    return round(bmi, 2), status


def compute_age(birth_date: Optional[date]) -> Optional[int]:
    """由出生日期派生当前年龄（按身份证周岁口径，未过今年生日则减一）。

    birth_date 缺失返回 None（此时回退到 User.age 兼容旧数据）。
    """
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


class UserService:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> User:
        """根据 ID 获取用户"""
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.settings),
                selectinload(User.goals),
            )
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException("用户不存在")
        return user

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        """根据邮箱获取用户"""
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_profile(
        db: AsyncSession, user_id: UUID, data: UserUpdate
    ) -> User:
        """更新用户资料（部分更新）"""
        user = await UserService.get_by_id(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def get_user_goals(db: AsyncSession, user_id: UUID) -> UserGoals:
        """获取用户目标（健身目标 + 营养目标 + 通知偏好），不存在则创建"""
        result = await db.execute(
            select(UserGoals).where(UserGoals.user_id == user_id)
        )
        goals = result.scalar_one_or_none()

        if not goals:
            goals = UserGoals(user_id=user_id)
            db.add(goals)
            await db.flush()
            await db.refresh(goals)

        return goals

    @staticmethod
    async def update_user_goals(
        db: AsyncSession, user_id: UUID, data: UserGoalsUpdate
    ) -> UserGoals:
        """更新用户目标（部分更新）"""
        goals = await UserService.get_user_goals(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(goals, field, value)

        await db.flush()
        await db.refresh(goals)
        return goals

    @staticmethod
    async def get_user_base_info(db: AsyncSession, user_id: UUID) -> UserSettings:
        """获取用户基础信息（当前身高/体重），不存在则创建"""
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        info = result.scalar_one_or_none()

        if not info:
            info = UserSettings(user_id=user_id)
            db.add(info)
            await db.flush()
            await db.refresh(info)

        return info

    @staticmethod
    async def update_user_base_info(
        db: AsyncSession,
        user_id: UUID,
        *,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
    ) -> UserSettings:
        """更新用户基础信息（当前身高/体重，部分更新）"""
        info = await UserService.get_user_base_info(db, user_id)
        if height_cm is not None:
            info.height_cm = height_cm
        if weight_kg is not None:
            info.weight_kg = weight_kg
        await db.flush()
        await db.refresh(info)
        return info

    @staticmethod
    async def list_health_metrics(
        db: AsyncSession, user_id: UUID, page: int = 1, size: int = 20
    ) -> tuple[list[HealthMetric], int]:
        """获取用户健康指标历史记录"""
        count_query = select(HealthMetric).where(HealthMetric.user_id == user_id)
        count_result = await db.execute(count_query)
        total = len(count_result.scalars().all())

        query = (
            select(HealthMetric)
            .where(HealthMetric.user_id == user_id)
            .order_by(HealthMetric.measure_date.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        result = await db.execute(query)
        metrics = list(result.scalars().all())

        return metrics, total

    @staticmethod
    async def get_health_metric(
        db: AsyncSession, user_id: UUID, metric_id: UUID
    ) -> HealthMetric:
        """获取单条健康指标"""
        result = await db.execute(
            select(HealthMetric)
            .where(HealthMetric.id == metric_id)
            .where(HealthMetric.user_id == user_id)
        )
        metric = result.scalar_one_or_none()

        if not metric:
            raise NotFoundException("健康指标记录不存在")

        return metric

    @staticmethod
    async def get_latest_health_metric(
        db: AsyncSession, user_id: UUID
    ) -> Optional[HealthMetric]:
        """获取最新的健康指标记录"""
        result = await db.execute(
            select(HealthMetric)
            .where(HealthMetric.user_id == user_id)
            .order_by(HealthMetric.measure_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _current_body(db: AsyncSession, user_id: UUID) -> tuple[Optional[float], Optional[float]]:
        """当前身高/体重：优先基础信息表快照，缺失回退最新 HealthMetric（兼容存量）。"""
        info = await UserService.get_user_base_info(db, user_id)
        height = float(info.height_cm) if info.height_cm else None
        weight = float(info.weight_kg) if info.weight_kg else None
        if height is None or weight is None:
            latest = await UserService.get_latest_health_metric(db, user_id)
            if height is None and latest and latest.height_cm:
                height = float(latest.height_cm)
            if weight is None and latest and latest.weight_kg:
                weight = float(latest.weight_kg)
        return height, weight

    @staticmethod
    async def get_body_summary(db: AsyncSession, user_id: UUID) -> dict:
        """构建用户身体数据摘要（身高/体重取当前基础信息，年龄/性别取 User）。

        供 create_plan / create_diet_plan 等需要用户身体数据的生成逻辑共用。
        """
        user = await UserService.get_by_id(db, user_id)
        height, weight = await UserService._current_body(db, user_id)
        return {
            "height_cm": height,
            "weight_kg": weight,
            "age": compute_age(user.birth_date) or user.age,
            "gender": user.gender,
        }

    @staticmethod
    def _compute_bmi(
        height_cm: Optional[float], weight_kg: Optional[float]
    ) -> Optional[float]:
        bmi, _ = compute_bmi(height_cm, weight_kg)
        return bmi

    @staticmethod
    async def get_profile_summary(db: AsyncSession, user_id: UUID) -> dict:
        """用户资料摘要（name/height/weight/age/gender/goal/bmi），供 get/update 共用。"""
        user = await UserService.get_by_id(db, user_id)
        height, weight = await UserService._current_body(db, user_id)
        return {
            "name": user.name,
            "height_cm": height,
            "weight_kg": weight,
            "birth_date": user.birth_date,
            "age": compute_age(user.birth_date) or user.age,
            "gender": user.gender,
            "goal": user.goals.goal if user.goals else None,
            "bmi": UserService._compute_bmi(height, weight),
        }

    @staticmethod
    async def update_profile_consolidated(
        db: AsyncSession,
        user_id: UUID,
        *,
        name: Optional[str] = None,
        birth_date: Optional[date] = None,
        gender: Optional[str] = None,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        goal: Optional[str] = None,
    ) -> None:
        """跨 User / UserGoals / UserSettings(基础信息) / HealthMetric 的资料更新（仅写入传入字段）。

        height/weight 作为当前值快照写入基础信息表，同时继续写入 HealthMetric 体重时序（保留趋势历史）；
        goal 写入 UserGoals；name/birth_date/gender 写入 User。
        """
        user_updates: dict = {}
        if name is not None:
            user_updates["name"] = name
        if birth_date is not None:
            user_updates["birth_date"] = birth_date
        if gender is not None:
            user_updates["gender"] = gender
        if user_updates:
            await UserService.update_profile(db, user_id, UserUpdate(**user_updates))

        if height_cm is not None or weight_kg is not None:
            latest = await UserService.get_latest_health_metric(db, user_id)
            resolved_height = (
                height_cm if height_cm is not None else (latest.height_cm if latest else None)
            )
            resolved_weight = (
                weight_kg if weight_kg is not None else (latest.weight_kg if latest else None)
            )
            # 当前值快照 → 基础信息表
            await UserService.update_user_base_info(
                db, user_id, height_cm=resolved_height, weight_kg=resolved_weight
            )
            # 时序记录 → HealthMetric（保留体重趋势）
            await UserService.create_health_metric(
                db,
                user_id,
                HealthMetricCreate(
                    measure_date=date.today(),
                    height_cm=resolved_height,
                    weight_kg=resolved_weight,
                ),
            )

        if goal is not None:
            await UserService.update_user_goals(
                db, user_id, UserGoalsUpdate(goal=goal)
            )

    @staticmethod
    async def create_health_metric(
        db: AsyncSession, user_id: UUID, data: HealthMetricCreate
    ) -> HealthMetric:
        """创建健康指标记录"""
        # 计算 BMI
        bmi, bmi_status = compute_bmi(data.height_cm, data.weight_kg)

        metric = HealthMetric(
            user_id=user_id,
            measure_date=data.measure_date,
            height_cm=data.height_cm,
            weight_kg=data.weight_kg,
            body_fat_pct=data.body_fat_pct,
            muscle_mass_kg=data.muscle_mass_kg,
            bmi=bmi,
            bmi_status=bmi_status,
            chest_cm=data.chest_cm,
            waist_cm=data.waist_cm,
            hip_cm=data.hip_cm,
            arm_cm=data.arm_cm,
            thigh_cm=data.thigh_cm,
            note=data.note,
        )
        db.add(metric)
        await db.flush()
        await db.refresh(metric)
        return metric

    @staticmethod
    async def update_health_metric(
        db: AsyncSession, user_id: UUID, metric_id: UUID, data: HealthMetricUpdate
    ) -> HealthMetric:
        """更新健康指标记录（部分更新）"""
        metric = await UserService.get_health_metric(db, user_id, metric_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(metric, field, value)

        # 重新计算 BMI（height_cm / weight_kg 任一提供时，另一值取当前记录，
        # 避免 `or` 吞掉合法的 0 值）
        if update_data.get("height_cm") is not None or update_data.get("weight_kg") is not None:
            height = update_data.get("height_cm") if update_data.get("height_cm") is not None else metric.height_cm
            weight = update_data.get("weight_kg") if update_data.get("weight_kg") is not None else metric.weight_kg
            bmi, bmi_status = compute_bmi(height, weight)
            metric.bmi = bmi
            metric.bmi_status = bmi_status

        await db.flush()
        await db.refresh(metric)
        return metric

    @staticmethod
    async def delete_health_metric(
        db: AsyncSession, user_id: UUID, metric_id: UUID
    ) -> None:
        """删除健康指标记录"""
        metric = await UserService.get_health_metric(db, user_id, metric_id)
        await db.delete(metric)
        await db.flush()
