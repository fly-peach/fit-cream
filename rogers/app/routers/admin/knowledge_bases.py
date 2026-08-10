"""
管理端知识库路由 /api/admin/knowledge-bases/*

提供管理员专用的知识库统计列表（统计列 + 搜索 + 分页）。
其余写操作（创建/编辑/删除/文档/索引/令牌）沿用 /api/knowledge-bases/*。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from src.fitme.models.user import User
from src.fitme.schemas.admin import AdminKbListItem
from src.fitme.schemas.common import PaginatedResponse, ResponseModel
from src.fitme.services.admin_service import AdminService

router = APIRouter(prefix="/knowledge-bases", tags=["admin-knowledge-bases"])


@router.get(
    "",
    response_model=ResponseModel[PaginatedResponse[AdminKbListItem]],
    operation_id="admin_list_knowledge_bases",
)
async def admin_list_knowledge_bases(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = Query(None, max_length=100, description="名称/slug 模糊搜索"),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """知识库列表（含文档/分块/待索引统计列）（admin）"""
    items, total = await AdminService.list_kbs_admin(
        db, page=page, size=size, keyword=keyword
    )
    return ResponseModel(
        data=PaginatedResponse(items=items, total=total, page=page, size=size)
    )
