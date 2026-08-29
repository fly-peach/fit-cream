"""
Agent 回调中间件

- TokenUsageMiddleware: 追踪 Token 使用量

每轮计数存入 AgentState（UntrackedValue，随 run 重置），而非实例属性--
避免共享 graph 下并发请求互相覆盖（根因 R2）。

注：对话持久化由 SSE 流（chat.py _run_agent_sse）同步落库，不在此处做异步
fire-and-forget。历史曾有的 ConversationPersistenceMiddleware 在 chat 路径从未
启用（仅被未使用的 create_agent_with_middleware 引用），已移除以避免误判。
"""

import logging
from typing import Annotated, Any, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from src.agents.harness.runtime.middleware.robust import state_hook_fail_open

logger = logging.getLogger("fitcream.agent")


class TokenUsageState(AgentState):
    """TokenUsageMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    token_prompt: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_completion: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_total: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    token_llm_calls: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]


class TokenUsageMiddleware(AgentMiddleware):
    """
    Token 使用量追踪中间件

    通过 after_model hook 追踪每次 LLM 调用的 Token 消耗。
    计数存入 AgentState，随每次 run 重置（UntrackedValue），并发安全。
    """

    state_schema = TokenUsageState  # type: ignore[assignment]

    def __init__(
        self,
        max_tokens_per_conversation: int = 50000,
        user_id: Optional[str] = None,
    ):
        super().__init__()
        self.max_tokens = max_tokens_per_conversation
        self.user_id = user_id

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        # 计数由 UntrackedValue 保证随 run 重置，此处仅日志
        logger.info(
            f"[TokenTracker] Started | max_tokens={self.max_tokens} | user={self.user_id}"
        )
        return None

    @state_hook_fail_open
    def after_model(self, state: TokenUsageState, runtime: Runtime) -> dict[str, Any] | None:
        # 从最近一条 AI 消息的 usage_metadata 中累积 token 用量
        usage: dict = {}
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}

        prompt = usage.get("input_tokens", 0)
        completion = usage.get("output_tokens", 0)
        total = usage.get("total_tokens", 0)

        llm_calls = state.get("token_llm_calls", 0) + 1
        new_prompt = state.get("token_prompt", 0) + prompt
        new_completion = state.get("token_completion", 0) + completion
        new_total = state.get("token_total", 0) + total

        pct = round(new_total / self.max_tokens * 100, 1) if self.max_tokens > 0 else 0
        logger.info(
            f"[TokenTracker] LLM #{llm_calls} tokens | "
            f"input={prompt} output={completion} "
            f"total={new_total}/{self.max_tokens} ({pct}%)"
        )

        # 超限时记录警告（不中断，由 SummarizationMiddleware 处理压缩）
        if new_total > self.max_tokens:
            logger.warning(
                f"[TokenTracker] Token limit exceeded: "
                f"{new_total}/{self.max_tokens} | user={self.user_id}"
            )

        return {
            "token_prompt": new_prompt,
            "token_completion": new_completion,
            "token_total": new_total,
            "token_llm_calls": llm_calls,
        }
