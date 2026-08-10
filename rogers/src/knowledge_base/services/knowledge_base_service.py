"""
知识库主体 Service（KB CRUD + 碰撞安全 slug）
"""
from __future__ import annotations

import re
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.knowledge_base.models.knowledge_base import KnowledgeBase
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