"""
管理端动作库检索质量路由 /api/admin/search-quality/*

提供动作库搜索召回评估与 embedding 回填触发：
- POST /eval：实时跑黄金集 Recall@K 评估（不落库，黄金集为版本化 JSON 文件）
- POST /backfill：触发 exercises.embedding 回填（后台异步任务）
- GET /backfill/status：回填任务运行状态

均 get_admin_user 保护，复用 AdminService 聚合模式。
"""
import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_admin_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.search_recall_service import SearchRecallService

logger = logging.getLogger("fitcream")

router = APIRouter(prefix="/search-quality", tags=["admin-search-quality"])

# 模块级回填任务状态（进程内；容器重启后丢失，属可接受——回填可随时重触）
_backfill_state: dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "result": None,
}


async def _run_backfill(force: bool) -> None:
    _backfill_state.update(
        running=True, started_at=time.time(), finished_at=None, result=None
    )
    try:
        _backfill_state["result"] = await SearchRecallService.backfill_embeddings(
            force=force
        )
    except Exception as e:
        logger.error("[SearchQuality] 回填任务异常: %s", e, exc_info=True)
        _backfill_state["result"] = {
            "ok": 0,
            "failed": 0,
            "message": f"回填任务异常: {e}",
        }
    finally:
        _backfill_state.update(running=False, finished_at=time.time())


@router.post(
    "/eval",
    response_model=ResponseModel[dict],
    operation_id="admin_search_quality_eval",
)
async def search_quality_eval(
    k: int = Query(20, ge=1, le=50, description="召回 K 值"),
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """实时跑黄金集 Recall@K 评估（admin）"""
    data = await SearchRecallService.evaluate(db, k=k)
    return ResponseModel(data=data)


@router.post(
    "/backfill",
    response_model=ResponseModel[dict],
    operation_id="admin_search_quality_backfill",
)
async def search_quality_backfill(
    force: bool = Query(False, description="是否全量重算（默认仅回填空值）"),
    _admin: User = Depends(get_admin_user),
):
    """触发动作库 embedding 回填（后台异步任务）（admin）"""
    if _backfill_state["running"]:
        return ResponseModel(
            data={
                "started": False,
                "running": True,
                "message": "回填任务已在运行中",
            }
        )
    asyncio.get_event_loop().create_task(_run_backfill(force))
    return ResponseModel(
        data={
            "started": True,
            "running": True,
            "message": "已触发动作库 embedding 回填（后台执行）",
        }
    )


@router.get(
    "/backfill/status",
    response_model=ResponseModel[dict],
    operation_id="admin_search_quality_backfill_status",
)
async def search_quality_backfill_status(
    _admin: User = Depends(get_admin_user),
):
    """查询回填任务运行状态（admin）"""
    return ResponseModel(data=dict(_backfill_state))
