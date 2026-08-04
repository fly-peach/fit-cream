"""记忆路由 /api/memory/* - 语义记忆只读查询"""
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user
from src.agents.harness.runtime.memory.store import get_memory_store
from src.agents.schemas.memory import SemanticMemoryOut
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel

logger = logging.getLogger("fitcream.memory")

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/semantic", response_model=ResponseModel[list[SemanticMemoryOut]])
async def list_semantic_memories(
    category: str | None = Query(None, description="按分类过滤：preference/fact/rule/status"),
    user: User = Depends(get_current_user),
):
    """
    获取当前用户的语义记忆列表（仅 active，按 updated_at 倒序）。

    数据来源为 MemoryStore（独立 MemoryBase，非 app Base）。
    若记忆系统启动初始化失败（lifespan 中异常被吞），
    get_memory_store() 会返回未 init_db 的实例，检索将报错 -> 此处兜底返回错误态。
    """
    try:
        store = get_memory_store()
        rows = await store.retrieve_semantic(
            user_id=str(user.id), category=category, limit=100
        )
        return ResponseModel(data=[SemanticMemoryOut.model_validate(r) for r in rows])
    except Exception as e:
        logger.exception("检索语义记忆失败")
        return JSONResponse(
            status_code=500,
            content={"code": 500, "message": f"检索语义记忆失败：{e}"},
        )
