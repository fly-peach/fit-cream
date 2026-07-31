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
from src.fitme.models.user_settings import UserSettings
from src.fitme.schemas.user import (
    HealthMetricCreate,
    HealthMetricUpdate,
    UserSettingsUpdate,
    UserUpdate,
)
from utils.exceptions import NotFoundException


class UserService:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> User:
        """根据 ID 获取用户"""
        result = await db.execute(
            select(User)
            .options(selectinload(User.settings))
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
    async def get_user_settings(db: AsyncSession, user_id: UUID) -> UserSettings:
        """获取用户设置，不存在则创建"""
        result = await db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        settings = result.scalar_one_or_none()

        if not settings:
            settings = UserSettings(user_id=user_id)
            db.add(settings)
            await db.flush()
            await db.refresh(settings)

        return settings

    @staticmethod
    async def update_user_settings(
        db: AsyncSession, user_id: UUID, data: UserSettingsUpdate
    ) -> UserSettings:
        """更新用户设置（部分更新）"""
        settings = await UserService.get_user_settings(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)

        await db.flush()
        await db.refresh(settings)
        return settings

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
    async def get_body_summary(db: AsyncSession, user_id: UUID) -> dict:
        """构建用户身体数据摘要（身高/体重取最新 HealthMetric，年龄/性别取 User）。

        供 create_plan / create_diet_plan 等需要用户身体数据的生成逻辑共用。
        """
        user = await UserService.get_by_id(db, user_id)
        latest = await UserService.get_latest_health_metric(db, user_id)
        return {
            "height_cm": float(latest.height_cm) if latest and latest.height_cm else None,
            "weight_kg": float(latest.weight_kg) if latest and latest.weight_kg else None,
            "age": user.age,
            "gender": user.gender,
        }

    @staticmethod
    def _compute_bmi(
        height_cm: Optional[float], weight_kg: Optional[float]
    ) -> Optional[float]:
        if not height_cm or not weight_kg:
            return None
        return round(weight_kg / ((height_cm / 100) ** 2), 1)

    @staticmethod
    async def get_profile_summary(db: AsyncSession, user_id: UUID) -> dict:
        """用户资料摘要（name/height/weight/age/gender/goal/bmi），供 get/update 共用。"""
        user = await UserService.get_by_id(db, user_id)
        latest = await UserService.get_latest_health_metric(db, user_id)
        height = float(latest.height_cm) if latest and latest.height_cm else None
        weight = float(latest.weight_kg) if latest and latest.weight_kg else None
        return {
            "name": user.name,
            "height_cm": height,
            "weight_kg": weight,
            "age": user.age,
            "gender": user.gender,
            "goal": user.settings.goal if user.settings else None,
            "bmi": UserService._compute_bmi(height, weight),
        }

    @staticmethod
    async def update_profile_consolidated(
        db: AsyncSession,
        user_id: UUID,
        *,
        name: Optional[str] = None,
        age: Optional[int] = None,
        gender: Optional[str] = None,
        height_cm: Optional[float] = None,
        weight_kg: Optional[float] = None,
        goal: Optional[str] = None,
    ) -> None:
        """跨 User / HealthMetric / UserSettings 三模型的资料更新（仅写入传入字段）。

        height/weight 作为时序记录写入 HealthMetric（缺省时携带上次值）；
        goal 写入 UserSettings；name/age/gender 写入 User。
        """
        user_updates: dict = {}
        if name is not None:
            user_updates["name"] = name
        if age is not None:
            user_updates["age"] = age
        if gender is not None:
            user_updates["gender"] = gender
        if user_updates:
            await UserService.update_profile(db, user_id, UserUpdate(**user_updates))

        if height_cm is not None or weight_kg is not None:
            latest = await UserService.get_latest_health_metric(db, user_id)
            await UserService.create_health_metric(
                db,
                user_id,
                HealthMetricCreate(
                    measure_date=date.today(),
                    height_cm=(
                        height_cm
                        if height_cm is not None
                        else (latest.height_cm if latest else None)
                    ),
                    weight_kg=(
                        weight_kg
                        if weight_kg is not None
                        else (latest.weight_kg if latest else None)
                    ),
                ),
            )

        if goal is not None:
            await UserService.update_user_settings(
                db, user_id, UserSettingsUpdate(goal=goal)
            )

    @staticmethod
    async def create_health_metric(
        db: AsyncSession, user_id: UUID, data: HealthMetricCreate
    ) -> HealthMetric:
        """创建健康指标记录"""
        # 计算 BMI
        bmi = None
        bmi_status = None
        if data.height_cm and data.weight_kg:
            bmi = data.weight_kg / ((data.height_cm / 100) ** 2)
            bmi_status = (
                "偏瘦" if bmi < 18.5
                else "正常" if bmi < 24
                else "偏胖" if bmi < 28
                else "肥胖"
            )

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

        # 重新计算 BMI
        if update_data.get("height_cm") or update_data.get("weight_kg"):
            height = update_data.get("height_cm") or metric.height_cm
            weight = update_data.get("weight_kg") or metric.weight_kg
            if height and weight:
                bmi = float(weight) / ((float(height) / 100) ** 2)
                bmi_status = (
                    "偏瘦" if bmi < 18.5
                    else "正常" if bmi < 24
                    else "偏胖" if bmi < 28
                    else "肥胖"
                )
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
