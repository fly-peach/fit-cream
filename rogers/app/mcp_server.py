"""
fastapi-mcp 集成（分权限 MCP 服务）

两个 MCP 实例（按 operation_id 分权限）：
- /mcp/read  只读 MCP（外部 agent 接入，认证: API Token）
- /mcp/admin 全权限 MCP（管理端，认证: JWT admin）

fastapi-mcp 0.4.0 默认转发 authorization 头，路由内通过 KB 权限依赖校验。
"""
import logging

from fastapi import FastAPI

from fastapi_mcp import FastApiMCP

logger = logging.getLogger("fitcream")

MCP_READ_OPERATIONS = [
    "list_knowledge_bases",
    "list_my_subscriptions",
    "get_knowledge_base",
    "list_documents",
    "get_document",
    "read_document",
    "search_documents",
    "get_graph",
    "get_document_references",
    "subscribe_kb",
    "unsubscribe_kb",
    "get_shared_kb",
    "get_public_kb",
]

MCP_ALL_OPERATIONS = MCP_READ_OPERATIONS + [
    "create_knowledge_base",
    "update_knowledge_base",
    "delete_knowledge_base",
    "set_kb_visibility",
    "create_document",
    "upload_document",
    "update_document_content",
    "update_document_metadata",
    "delete_document",
    "reindex_knowledge_base",
    "rebuild_graph",
    "lint_knowledge_base",
    "list_subscribers",
    "remove_subscriber",
    "create_kb_token",
    "list_kb_tokens",
    "revoke_kb_token",
]


def setup_mcp(app: FastAPI) -> None:
    """挂载两个分权限 MCP 实例到 FastAPI app。

    若 fastapi-mcp 不支持多实例挂载（路径冲突），则降级为单 admin 实例。
    """
    try:
        # 1. 只读 MCP（外部 agent 接入，认证: API Token / JWT）
        mcp_read = FastApiMCP(
            app,
            name="FitCream KB Reader",
            description="知识库只读 MCP 服务（外部 agent 接入）",
            include_operations=MCP_READ_OPERATIONS,
        )
        mcp_read.mount_http(mount_path="/mcp/read")
        logger.info("MCP 只读端点已挂载: /mcp/read (%d operations)", len(MCP_READ_OPERATIONS))

        # 2. 全权限 MCP（管理端，认证: JWT admin）
        mcp_admin = FastApiMCP(
            app,
            name="FitCream KB Admin",
            description="知识库管理 MCP 服务（管理员全权限）",
            include_operations=MCP_ALL_OPERATIONS,
        )
        mcp_admin.mount_http(mount_path="/mcp/admin")
        logger.info("MCP 管理端点已挂载: /mcp/admin (%d operations)", len(MCP_ALL_OPERATIONS))
    except Exception as e:
        logger.warning("MCP 多实例挂载失败，降级为单实例: %s", e)
        try:
            mcp_admin = FastApiMCP(
                app,
                name="FitCream KB",
                description="知识库 MCP 服务",
                include_operations=MCP_ALL_OPERATIONS,
            )
            mcp_admin.mount_http(mount_path="/mcp/admin")
            logger.info("MCP 降级单实例已挂载: /mcp/admin")
        except Exception as e2:
            logger.error("MCP 挂载完全失败: %s", e2)
