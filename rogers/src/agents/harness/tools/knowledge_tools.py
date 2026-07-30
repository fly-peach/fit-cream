"""
知识库检索工具

供 Agent 调用，检索知识库内容。
遵循现有 plan_tools.py 的 @tool + async_session_factory() 模式（同进程融合）。
"""
from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.database import async_session_factory
from src.knowledge_base.service import KnowledgeBaseService


class SearchKBInput(BaseModel):
    """搜索知识库的输入参数"""
    query: str = Field(description="搜索关键词，如'哑铃卧推'、'蛋白质摄入'、'减脂原理'")
    kb_id: Optional[str] = Field(
        default=None,
        description="指定知识库 ID（须为用户已订阅的 KB）。不填则搜索用户已订阅的全部知识库",
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
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)

            if kb_id:
                # 指定 KB：仅当用户已订阅时才搜索（订阅即 Agent 搜索范围）
                subscribed_ids = await KnowledgeBaseService.get_subscribed_kb_ids(db, uid)
                if UUID(kb_id) not in subscribed_ids:
                    return {
                        "success": True,
                        "total": 0,
                        "results": [],
                        "message": f"未订阅知识库 {kb_id}，请先订阅后再搜索",
                    }
                results = await KnowledgeBaseService.search_documents(
                    db, UUID(kb_id), query, limit
                )
            else:
                # 搜索用户已订阅的全部知识库
                kbs = await KnowledgeBaseService.list_my_subscriptions(db, uid)
                all_results = []
                for kb in kbs:
                    r = await KnowledgeBaseService.search_documents(
                        db, kb.id, query, limit
                    )
                    all_results.extend(r)
                # 按相关度排序，取 top limit
                all_results.sort(key=lambda x: x.get("rank", 0), reverse=True)
                results = all_results[:limit]

            if not results:
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
        except Exception as e:
            return {"success": False, "error": str(e)}


class ReadKBDocumentInput(BaseModel):
    """读取知识库文档的输入参数"""
    document_id: str = Field(description="文档 ID（从 search_knowledge_base 结果中获取）")
    kb_id: Optional[str] = Field(
        default=None,
        description="知识库 ID。如果文档 ID 已包含完整路径可不填",
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
    user_id = None
    if config and "configurable" in config:
        user_id = config["configurable"].get("user_id")

    if not user_id:
        return {"success": False, "error": "缺少用户身份信息"}

    async with async_session_factory() as db:
        try:
            uid = UUID(user_id)
            # 校验访问权限：仅 KB 所有者或已订阅者可读，防止 IDOR 枚举
            doc = await KnowledgeBaseService.get_document_for_user(
                db, UUID(document_id), uid
            )
            return {
                "success": True,
                "document": {
                    "id": str(doc.id),
                    "title": doc.title,
                    "filename": doc.filename,
                    "path": doc.path,
                    "content": doc.content,
                    "tags": doc.tags or [],
                    "entity_type": doc.entity_type,
                    "file_type": doc.file_type,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
                },
                "message": f"已读取文档「{doc.title}」",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
