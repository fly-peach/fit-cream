"""
FitCream Agent Middleware

基于 LangChain AgentMiddleware API 的中间件：
- 日志记录：记录所有 LLM 调用和 Tool 执行
- 限流：限制单次对话的 Tool/LLM 调用次数
- Token 追踪：追踪和限制 Token 使用量
- 意图识别：渐进式提示词注入（IntentMiddleware）
- 技能管理：catalog 烘焙进 system_prompt（SkillsMiddleware，纯占位）

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
from src.agents.harness.runtime.middleware.intent_middleware import (
    IntentMiddleware,
    detect_intent,
)
from src.agents.harness.runtime.middleware.skills_middleware import SkillsMiddleware

__all__ = [
    "AgentLoggingMiddleware",
    "SameToolLimitMiddleware",
    "create_rate_limit_middleware",
    "TokenUsageMiddleware",
    "IntentMiddleware",
    "detect_intent",
    "SkillsMiddleware",
]
