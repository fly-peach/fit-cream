"""
FitCream Agent Middleware

基于 LangChain AgentMiddleware API 的中间件：
- 日志记录：记录所有 LLM 调用和 Tool 执行
- 限流：限制单次对话的 Tool/LLM 调用次数
- Token 追踪：追踪和限制 Token 使用量
- 用户请求门控：意图识别渐进式注入 + 知识库回答开关（RequestGateMiddleware）
- 技能管理：catalog 烘焙进 system_prompt（无独立中间件，纯静态）

注：对话持久化由 SSE 流（chat.py _run_agent_sse）同步落库，
不经中间件（历史 ConversationPersistenceMiddleware / create_agent_middleware
仅在未启用的 per-user 路径用，已移除）。
"""

from src.agents.harness.runtime.middleware.logging_middleware import AgentLoggingMiddleware
from src.agents.harness.runtime.middleware.rate_limit import (
    SameToolLimitMiddleware,
    create_rate_limit_middleware,
)
from src.agents.harness.runtime.middleware.callbacks import TokenUsageMiddleware
from src.agents.harness.runtime.middleware.request_gate_middleware import (
    RequestGateMiddleware,
    detect_intent,
    detect_intents,
)
from src.agents.harness.runtime.middleware.transient_prompt import (
    TransientPromptMiddleware,
)

__all__ = [
    "AgentLoggingMiddleware",
    "SameToolLimitMiddleware",
    "create_rate_limit_middleware",
    "TokenUsageMiddleware",
    "RequestGateMiddleware",
    "detect_intent",
    "detect_intents",
    "TransientPromptMiddleware",
]
