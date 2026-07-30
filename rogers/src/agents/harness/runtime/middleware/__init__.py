"""
FitCream Agent Middleware

基于 LangChain AgentMiddleware API 的中间件：
- 日志记录：记录所有 LLM 调用和 Tool 执行
- 限流：限制单次对话的 Tool/LLM 调用次数
- Token 追踪：追踪和限制 Token 使用量
- 对话持久化：将对话保存到 Conversation 表
- 意图识别：渐进式提示词注入（IntentMiddleware）

使用方式：
    from src.agents.harness.runtime.middleware import create_agent_middleware

    middleware = create_agent_middleware(user_id="xxx", thread_id="yyy")
    agent = create_agent(model=..., tools=[...], middleware=middleware)
"""

from src.agents.harness.runtime.middleware.logging_middleware import AgentLoggingMiddleware
from src.agents.harness.runtime.middleware.rate_limit import (
    SameToolLimitMiddleware,
    create_rate_limit_middleware,
)
from src.agents.harness.runtime.middleware.callbacks import (
    ConversationPersistenceMiddleware,
    TokenUsageMiddleware,
    create_agent_middleware,
)
from src.agents.harness.runtime.middleware.intent_middleware import (
    IntentMiddleware,
    detect_intent,
)

__all__ = [
    "AgentLoggingMiddleware",
    "SameToolLimitMiddleware",
    "create_rate_limit_middleware",
    "ConversationPersistenceMiddleware",
    "TokenUsageMiddleware",
    "create_agent_middleware",
    "IntentMiddleware",
    "detect_intent",
]
