"""
Agent 日志中间件

使用 LangChain AgentMiddleware hooks 记录：
- LLM 调用开始/结束
- Tool 调用开始/结束
- 错误和异常
- Token 使用量

每轮计数（LLM/Tool 调用数、开始时间）存入 AgentState（UntrackedValue，
随 run 重置），而非实例属性——避免共享 graph 下并发请求互相覆盖。
"""

import logging
import time
from typing import Annotated, Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langchain.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from langgraph.types import Command
from typing_extensions import NotRequired

from src.agents.harness.runtime.middleware.robust import (
    model_hook_fail_open,
    state_hook_fail_open,
)

# 异步 handler 类型
AsyncToolHandler = Callable[[ToolCallRequest], Any]  # Awaitable[ToolMessage | Command]

logger = logging.getLogger("fitcream.agent")


class AgentLoggingState(AgentState):
    """AgentLoggingMiddleware 的每轮状态（不持久化到 checkpoint，随 run 重置）。"""

    log_llm_calls: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    log_tool_calls: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    log_start_time: NotRequired[Annotated[float, UntrackedValue, PrivateStateAttr]]


class AgentLoggingMiddleware(AgentMiddleware):
    """
    Agent 日志中间件

    通过 before_model / after_model / wrap_tool_call hooks
    记录所有 LLM 和 Tool 调用的详细日志。
    """

    state_schema = AgentLoggingState  # type: ignore[assignment]

    def __init__(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        verbose: bool = False,
    ):
        super().__init__()
        self.user_id = user_id
        self.thread_id = thread_id
        self.verbose = verbose

    def _log_prefix(self) -> str:
        # user_id / thread_id 现由 ContextVar 经格式化器注入为顶层字段/前缀，
        # 不再拼入 message 文本，避免与日志平台索引重复。
        return "[Agent]"

    @state_hook_fail_open
    def before_agent(self, state: AgentLoggingState, runtime: Runtime) -> dict[str, Any] | None:
        logger.info(f"{self._log_prefix()} Agent started")
        # 初始化每轮计数（UntrackedValue 不跨 run 持久化，显式置零保证干净）
        return {
            "log_start_time": time.time(),
            "log_llm_calls": 0,
            "log_tool_calls": 0,
        }

    @state_hook_fail_open
    def before_model(self, state: AgentLoggingState, runtime: Runtime) -> dict[str, Any] | None:
        llm_calls = state.get("log_llm_calls", 0)
        msg_count = len(state.get("messages", []))
        logger.info(
            f"{self._log_prefix()} LLM call #{llm_calls + 1} | messages={msg_count}"
        )
        # verbose 模式下输出最后一条消息预览（调试用）
        if self.verbose and state.get("messages"):
            last_msg = state["messages"][-1]
            content_preview = str(getattr(last_msg, "content", ""))[:100]
            logger.debug(f"  last_message: {content_preview}...")
        return None

    @state_hook_fail_open
    def after_model(self, state: AgentLoggingState, runtime: Runtime) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        tool_call_count = 0
        if messages:
            last = messages[-1]
            # usage_metadata 在非流式调用时存在，流式时由 ChatQwen/ChatDeepSeek 补全
            usage = getattr(last, "usage_metadata", None) or {}
            tokens = usage.get("total_tokens", "N/A")
            if self.verbose:
                # 内容预览仅调试模式记录，避免对话隐私写入日志
                content_preview = str(getattr(last, "content", ""))[:100]
                logger.info(
                    f"{self._log_prefix()} LLM responded | "
                    f"tokens={tokens} | response='{content_preview}...'"
                )
            else:
                logger.info(f"{self._log_prefix()} LLM responded | tokens={tokens}")
            tool_calls = getattr(last, "tool_calls", None) or []
            tool_call_count = len(tool_calls)

        # 累计本轮 LLM 调用数 + Tool 调用请求数（写入 state）
        return {
            "log_llm_calls": state.get("log_llm_calls", 0) + 1,
            "log_tool_calls": state.get("log_tool_calls", 0) + tool_call_count,
        }

    @model_hook_fail_open
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        tool_name = request.tool_call["name"]

        logger.info(f"{self._log_prefix()} Tool started | tool={tool_name}")
        if self.verbose:
            args_preview = str(request.tool_call.get("args", {}))[:200]
            logger.debug(f"  args: {args_preview}...")

        start = time.time()
        try:
            result = handler(request)
            duration = (time.time() - start) * 1000
            if self.verbose:
                output_preview = str(getattr(result, "content", result))[:200]
                logger.debug(f"  output: {output_preview}...")
            logger.info(
                f"{self._log_prefix()} Tool ended ✓ | "
                f"tool={tool_name} | duration={duration:.1f}ms"
            )
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                f"{self._log_prefix()} Tool error ✗ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"error={type(e).__name__}: {str(e)[:200]}"
            )
            raise

    @model_hook_fail_open
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: AsyncToolHandler,
    ) -> ToolMessage | Command:
        tool_name = request.tool_call["name"]

        logger.info(f"{self._log_prefix()} Tool started | tool={tool_name}")
        if self.verbose:
            args_preview = str(request.tool_call.get("args", {}))[:200]
            logger.debug(f"  args: {args_preview}...")

        start = time.time()
        try:
            result = await handler(request)
            duration = (time.time() - start) * 1000
            if self.verbose:
                output_preview = str(getattr(result, "content", result))[:200]
                logger.debug(f"  output: {output_preview}...")
            logger.info(
                f"{self._log_prefix()} Tool ended ✓ | "
                f"tool={tool_name} | duration={duration:.1f}ms"
            )
            return result
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(
                f"{self._log_prefix()} Tool error ✗ | "
                f"tool={tool_name} | duration={duration:.1f}ms | "
                f"error={type(e).__name__}: {str(e)[:200]}"
            )
            raise

    @state_hook_fail_open
    def after_agent(self, state: AgentLoggingState, runtime: Runtime) -> dict[str, Any] | None:
        start_time = state.get("log_start_time", 0.0)
        duration = (time.time() - start_time) * 1000 if start_time else 0.0
        logger.info(
            f"{self._log_prefix()} Agent ended | "
            f"duration={duration:.1f}ms | "
            f"llm_calls={state.get('log_llm_calls', 0)} | "
            f"tool_calls={state.get('log_tool_calls', 0)}"
        )
        return None
