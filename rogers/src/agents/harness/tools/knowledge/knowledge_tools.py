"""
知识库检索工具

供 Agent 调用，检索知识库内容。
遵循现有 plan_tools.py 的 @tool + session_scope() 模式（同进程融合）。
"""
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.knowledge_base.embeddings import semantic_available
from src.knowledge_base.services.document_service import KBDocumentService
from src.knowledge_base.services.knowledge_base_service import KnowledgeBaseService
from src.knowledge_base.services.search_service import KBSearchService


class SearchKBInput(BaseModel):
    """搜索知识库的输入参数"""
    query: str = Field(description="搜索关键词，如'哑铃卧推'、'蛋白质摄入'、'减脂原理'")
    kb_id: Optional[str] = Field(
        default=None,
        description="指定知识库 ID（须为用户已订阅或自有的 KB）。不填则搜索用户已订阅及自有的全部知识库",
    )
    limit: int = Field(default=5, ge=1, le=20, description="返回结果数量，默认5条")


@tool(args_schema=SearchKBInput)
async def search_knowledge_base(
    query: str,
    kb_id: Optional[str] = None,
    limit: int = 5,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    搜索知识库中的相关内容。

    使用场景：
    - 用户询问健身知识、训练原理、营养信息等问题时，先搜索知识库获取权威信息再回答
    - 用户问"哑铃卧推怎么做" -> 搜索"哑铃卧推"
    - 用户问"蛋白质每天吃多少" -> 搜索"蛋白质摄入"
    - 用户问"减脂原理是什么" -> 搜索"减脂原理"

    返回搜索结果（含文档标题、分块内容、面包屑路径）。

    Returns:
        包含搜索结果列表的字典
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            results = await KBSearchService.search_across_subscriptions(
                db, user_id, query, UUID(kb_id) if kb_id else None, limit
            )
            semantic = await semantic_available(db)
    except Exception as e:
        return error_response(e)

    if not results:
        if not semantic:
            return {
                "success": True,
                "total": 0,
                "results": [],
                "degraded": True,
                "degraded_reason": "semantic_unavailable",
                "message": (
                    f"知识库中未找到与「{query}」相关的内容，且当前检索能力受限"
                    "（语义检索不可用，仅关键词匹配）。"
                ),
            }
        return {
            "success": True,
            "total": 0,
            "results": [],
            "message": f"知识库中未找到与「{query}」相关的内容",
        }

    return {
        "success": True,
        "total": len(results),
        "results": results,
        "message": f"找到 {len(results)} 条与「{query}」相关的知识库内容",
    }


class ListMyKBInput(BaseModel):
    """列出我的知识库（无输入参数）"""


@tool(args_schema=ListMyKBInput)
async def list_my_knowledge_bases(
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    列出当前用户可访问的知识库（已订阅 + 自己创建的）。

    使用场景：
    - 用户问"我订阅了哪些知识库"、"看看我的知识库"、"有哪些知识库"时使用
    - 用户想了解自己在知识库上的订阅情况

    返回知识库列表（含名称、ID、描述、是否已订阅、是否本人创建）。

    Returns:
        包含知识库列表的字典
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            kbs = await KnowledgeBaseService.list_my_accessible_kbs(db, user_id)
            subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, user_id)
    except Exception as e:
        return error_response(e)

    items = [
        {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description or "",
            "slug": kb.slug,
            "subscribed": kb.id in subscribed_ids,
            "is_owner": kb.owner_id == user_id,
        }
        for kb in kbs
    ]
    if not items:
        return {
            "success": True,
            "total": 0,
            "knowledge_bases": [],
            "message": "您当前没有可访问的知识库。可在知识库页面订阅，或请管理员创建",
        }
    return {
        "success": True,
        "total": len(items),
        "knowledge_bases": items,
        "message": f"您共有 {len(items)} 个可访问的知识库",
    }


class ReadKBDocumentInput(BaseModel):
    """读取知识库文档的输入参数"""
    document_id: str = Field(description="文档 ID（从 search_knowledge_base 结果中获取）")
    kb_id: Optional[str] = Field(
        default=None,
        description="知识库 ID（可选）。提供时校验文档归属，防止跨库读取",
    )


@tool(args_schema=ReadKBDocumentInput)
async def read_kb_document(
    document_id: str,
    kb_id: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    读取知识库中的完整文档内容。

    使用场景：
    - search_knowledge_base 找到相关文档后，需要读取完整内容以提供详细回答
    - 用户指定查看某个文档时

    Returns:
        包含文档标题、完整内容、元数据的字典
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    try:
        async with session_scope() as db:
            doc = await KBDocumentService.get_document_for_user(
                db, UUID(document_id), user_id
            )
            if kb_id and str(doc.kb_id) != kb_id:
                return {
                    "success": False,
                    "error": f"文档 {document_id} 不属于知识库 {kb_id}",
                    "message": "文档不属于指定知识库，请核对后重试",
                }
            return {
                "success": True,
                "document": {
                    "id": str(doc.id),
                    "kb_id": str(doc.kb_id),
                    "title": doc.title,
                    "filename": doc.filename,
                    "path": doc.path,
                    "content": doc.content,
                    "tags": doc.tags or [],
                    "entity_type": doc.entity_type,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                },
                "message": f"已读取文档「{doc.title}」",
            }
    except Exception as e:
        return error_response(e)
