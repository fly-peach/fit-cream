"""
记忆更新中间件 (Memory Update Middleware)

当对话 token 累计达到阈值时，自动触发记忆提取和存储。
基于 MemoryPipeline 实现分层认知记忆的自动化管理。

工作流程：
1. after_model hook 追踪 token 使用量
2. 当累计 token 超过 trigger_tokens (默认 20K) 时触发
3. 异步调用 MemoryPipeline.process_conversation 提取记忆
4. 重置计数器，等待下一次触发

用法：
    from agents.harness.middleware.memory_update import MemoryUpdateMiddleware

    middleware = MemoryUpdateMiddleware(
        user_id="user-123",
        thread_id="thread-456",
        trigger_tokens=20_000,
    )
"""

import asyncio
import logging
from typing import Any, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime

logger = logging.getLogger("fitcream.memory")


class MemoryUpdateMiddleware(AgentMiddleware):
    """
    记忆更新中间件

    在对话过程中，当 token 使用量达到阈值时自动提取记忆。
    使用 MemoryPipeline 进行分层记忆提取（情景/语义/程序性）。

    触发条件：
    - 累计 token 数超过 trigger_tokens（默认 20,000）
    - 每次触发后重置计数器

    注意事项：
    - 记忆提取是异步后台任务，不阻塞主对话流
    - 需要 user_id 才能正确关联记忆
    - 如果没有配置 MemoryPipeline，会静默跳过
    """

    def __init__(
        self,
        user_id: str,
        thread_id: Optional[str] = None,
        trigger_tokens: int = 20_000,
    ):
        """
        初始化记忆更新中间件

        Args:
            user_id: 用户 ID（必需，用于关联记忆）
            thread_id: 对话线程 ID
            trigger_tokens: 触发记忆更新的 token 阈值（默认 20K）
        """
        super().__init__()
        self.user_id = user_id
        self.thread_id = thread_id
        self.trigger_tokens = trigger_tokens

        self._accumulated_tokens: int = 0
        self._messages_since_last_update: int = 0
        self._is_processing: bool = False

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 开始前重置计数器"""
        self._accumulated_tokens = 0
        self._messages_since_last_update = 0
        return None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        每次 LLM 调用后检查 token 使用量

        当累计 token 超过阈值时，触发异步记忆提取。
        """
        messages = state.get("messages", [])
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}
            total_tokens = usage.get("total_tokens", 0)
            self._accumulated_tokens += total_tokens
            self._messages_since_last_update += 1

        # 检查是否达到触发阈值
        if self._accumulated_tokens >= self.trigger_tokens and not self._is_processing:
            logger.info(
                f"[MemoryUpdate] Trigger threshold reached: "
                f"{self._accumulated_tokens}/{self.trigger_tokens} tokens | "
                f"user={self.user_id[:8]} | messages={self._messages_since_last_update}"
            )
            self._trigger_memory_extraction(state)
            # 重置计数器
            self._accumulated_tokens = 0
            self._messages_since_last_update = 0

        return None

    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Agent 结束后，如果有未处理的对话也触发记忆提取

        确保即使未达到 token 阈值，对话结束时也能提取记忆。
        """
        # 如果有消息积累但未触发过，在对话结束时也处理
        if self._messages_since_last_update > 0 and not self._is_processing:
            self._trigger_memory_extraction(state)
            self._accumulated_tokens = 0
            self._messages_since_last_update = 0
        return None

    def _trigger_memory_extraction(self, state: AgentState) -> None:
        """
        触发异步记忆提取

        在后台运行，不阻塞主对话流。
        """
        self._is_processing = True
        messages = state.get("messages", [])

        if not messages:
            self._is_processing = False
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._extract_memories(messages))
        except RuntimeError:
            # 没有运行中的事件循环，同步执行
            asyncio.run(self._extract_memories(messages))
        finally:
            self._is_processing = False

    async def _extract_memories(self, messages: list) -> None:
        """
        执行记忆提取

        使用 MemoryPipeline 处理对话消息，提取并存储记忆。
        """
        try:
            from agents.harness.memory.pipeline import get_memory_pipeline

            pipeline = get_memory_pipeline()

            # 检查 pipeline 是否配置了 extractor
            if pipeline.extractor is None:
                logger.debug("[MemoryUpdate] No extractor configured, skipping")
                return

            stats = await pipeline.process_conversation(
                user_id=self.user_id,
                messages=messages,
                thread_id=self.thread_id,
            )

            logger.info(
                f"[MemoryUpdate] Memory extraction completed | "
                f"user={self.user_id[:8]} | "
                f"episodic={stats.get('episodic', 0)} | "
                f"semantic={stats.get('semantic', 0)} | "
                f"procedural={stats.get('procedural', 0)}"
            )

        except ImportError as e:
            logger.warning(f"[MemoryUpdate] Memory module not available: {e}")
        except Exception as e:
            logger.error(f"[MemoryUpdate] Memory extraction failed: {e}")


def create_memory_update_middleware(
    user_id: str,
    thread_id: Optional[str] = None,
    trigger_tokens: int = 20_000,
) -> MemoryUpdateMiddleware:
    """
    工厂函数：创建记忆更新中间件

    Args:
        user_id: 用户 ID
        thread_id: 对话线程 ID
        trigger_tokens: 触发阈值（默认 20K）

    Returns:
        MemoryUpdateMiddleware 实例
    """
    return MemoryUpdateMiddleware(
        user_id=user_id,
        thread_id=thread_id,
        trigger_tokens=trigger_tokens,
    )