"""
知识库主体 Service（KB CRUD + 碰撞安全 slug + 订阅管理 + 读权限校验）
"""
from __future__ import annotations

import re
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.knowledge_base.models.knowledge_base import KnowledgeBase
from src.knowledge_base.models.subscription import KBSubscription
from utils.exceptions import NotFoundException


class KnowledgeBaseService:
    @staticmethod
    async def create_kb(
        db: AsyncSession, owner_id: UUID, name: str, description: str = "", schema_config: Optional[dict] = None
    ) -> KnowledgeBase:
        """创建知识库（含碰撞安全 slug）"""
        slug = await KnowledgeBaseService._generate_unique_slug(db, name, owner_id)
        kb = KnowledgeBase(
            name=name,
            description=description,
            slug=slug,
            owner_id=owner_id,
            schema_config=schema_config or {},
        )
        db.add(kb)
        await db.flush()
        return kb

    @staticmethod
    async def _generate_unique_slug(db: AsyncSession, name: str, owner_id: UUID) -> str:
        """碰撞安全 slug 生成（参考 LLM Wiki generate_slug）"""
        base = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        if not base:
            base = "untitled"

        candidate = base
        counter = 0
        while True:
            result = await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.slug == candidate)
            )
            if not result.scalar_one_or_none():
                return candidate
            counter += 1
            candidate = f"{base}-{counter}"

    @staticmethod
    async def list_kbs(db: AsyncSession) -> List[KnowledgeBase]:
        """返回全部知识库（登录用户可读任意 KB）。"""
        result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def get_kb(db: AsyncSession, kb_id: UUID) -> KnowledgeBase:
        result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
        kb = result.scalar_one_or_none()
        if not kb:
            raise NotFoundException("知识库不存在")
        return kb

    @staticmethod
    async def ensure_kb_access(
        db: AsyncSession, kb_id: UUID, user_id: UUID, role: Optional[str] = None
    ) -> None:
        """读权限校验：admin 全局放行；KB 所有者或已订阅者放行；未授权统一抛 NotFoundException。"""
        if role == "admin":
            return
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        if kb.owner_id == user_id:
            return
        subscribed = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
        if kb.id not in subscribed:
            raise NotFoundException("知识库不存在")

    @staticmethod
    async def update_kb(
        db: AsyncSession, kb_id: UUID, name: Optional[str] = None,
        description: Optional[str] = None, schema_config: Optional[dict] = None,
    ) -> KnowledgeBase:
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description
        if schema_config is not None:
            kb.schema_config = schema_config
        await db.flush()
        return kb

    @staticmethod
    async def delete_kb(db: AsyncSession, kb_id: UUID) -> None:
        kb = await KnowledgeBaseService.get_kb(db, kb_id)
        await db.delete(kb)
        await db.flush()

    # ============================================================
    # 订阅管理（完整权限门槛型）
    # ============================================================

    @staticmethod
    async def subscribe(
        db: AsyncSession, kb_id: UUID, user_id: UUID
    ) -> KBSubscription:
        """用户自助订阅知识库（幂等：已订阅则返回现有记录）"""
        await KnowledgeBaseService.get_kb(db, kb_id)
        result = await db.execute(
            select(KBSubscription).where(
                KBSubscription.kb_id == kb_id, KBSubscription.user_id == user_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            return sub
        sub = KBSubscription(kb_id=kb_id, user_id=user_id)
        db.add(sub)
        await db.flush()
        return sub

    @staticmethod
    async def unsubscribe(db: AsyncSession, kb_id: UUID, user_id: UUID) -> None:
        """取消订阅（幂等：未订阅也不报错）"""
        result = await db.execute(
            select(KBSubscription).where(
                KBSubscription.kb_id == kb_id, KBSubscription.user_id == user_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            await db.delete(sub)
            await db.flush()

    @staticmethod
    async def get_subscribed_kb_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
        """返回用户已订阅的 KB ID 集合（供 list 标记 subscribed 态 + 读权限校验 + Agent 搜索范围）"""
        result = await db.execute(
            select(KBSubscription.kb_id).where(KBSubscription.user_id == user_id)
        )
        return {row[0] for row in result.all()}

    @staticmethod
    async def get_owned_kb_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
        """返回用户作为 owner 的 KB ID 集合"""
        result = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.owner_id == user_id)
        )
        return {row[0] for row in result.all()}

    @staticmethod
    async def get_accessible_kb_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
        """返回用户可读的全部 KB ID（已订阅 ∪ 自有），与 ensure_kb_access 权限口径一致"""
        return (
            await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
        ) | (await KnowledgeBaseService.get_owned_kb_ids(db, user_id))

    @staticmethod
    async def list_my_subscriptions(
        db: AsyncSession, user_id: UUID
    ) -> List[KnowledgeBase]:
        """返回用户已订阅的知识库列表"""
        subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
        if not subscribed_ids:
            return []
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.id.in_(subscribed_ids))
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_my_accessible_kbs(
        db: AsyncSession, user_id: UUID
    ) -> List[KnowledgeBase]:
        """返回用户可访问的知识库列表（已订阅 ∪ 自有），Agent 列表工具使用"""
        accessible_ids = await KnowledgeBaseService.get_accessible_kb_ids(db, user_id)
        if not accessible_ids:
            return []
        result = await db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.id.in_(accessible_ids))
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_subscribers(
        db: AsyncSession, kb_id: UUID
    ) -> List[KBSubscription]:
        """列出某 KB 的全部订阅者（admin，含用户信息）"""
        result = await db.execute(
            select(KBSubscription)
            .options(selectinload(KBSubscription.user))
            .where(KBSubscription.kb_id == kb_id)
            .order_by(KBSubscription.subscribed_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def remove_subscriber(
        db: AsyncSession, kb_id: UUID, user_id: UUID
    ) -> None:
        """admin 踢出某订阅者（幂等）"""
        await KnowledgeBaseService.unsubscribe(db, kb_id, user_id)