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
                bmi = weight / ((height / 100) ** 2)
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
