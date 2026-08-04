"""
记忆更新中间件 (Memory Update Middleware)

当对话 token 累计达到阈值时，自动触发记忆提取和存储。
基于 MemoryPipeline 实现分层认知记忆的自动化管理。

工作流程：
1. after_model hook 追踪 token 使用量（存入 AgentState）
2. 当累计 token 超过 trigger_tokens (默认 100K) 时触发
3. 异步调用 MemoryPipeline.process_conversation 提取记忆
4. 重置计数器，等待下一次触发

两种部署形态：
- per-user 实例：__init__ 传入 user_id/thread_id（如 create_agent_with_middleware）
- 共享 graph 单例：__init__ 留空，运行时从 RunnableConfig.configurable 解析
  user_id，thread_id 再回退到 runtime.execution_info。适配生产环境所有用户复用
  同一编译后 graph 的场景。

每轮 token 计数存入 AgentState（UntrackedValue，随 run 重置），并发安全。
防重入以 user_id 为键维护集合（共享实例下并发用户互不干扰）；后台任务在
done_callback 中按 user_id 清理键值（修 1.8 竞态），不再使用 asyncio.run 兜底
（修 1.9 死分支）。

用法：
    # per-user
    middleware = MemoryUpdateMiddleware(
        user_id="user-123", thread_id="thread-456", trigger_tokens=100_000,
    )
    # 共享 graph（运行时解析）
    middleware = MemoryUpdateMiddleware(trigger_tokens=100_000)
"""

import asyncio
import logging
from typing import Annotated, Any, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langgraph.channels.untracked_value import UntrackedValue
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

logger = logging.getLogger("fitcream.memory")


class MemoryUpdateState(AgentState):
    """MemoryUpdateMiddleware 的每轮状态（不持久化到 checkpoint）。"""

    memory_accumulated_tokens: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]
    memory_messages_since_update: NotRequired[Annotated[int, UntrackedValue, PrivateStateAttr]]


class MemoryUpdateMiddleware(AgentMiddleware):
    """
    记忆更新中间件

    在对话过程中，当 token 使用量达到阈值时自动提取记忆。
    使用 MemoryPipeline 进行分层记忆提取（情景/语义/程序性）。

    触发条件：
    - 累计 token 数超过 trigger_tokens（默认 100,000）
    - 每次触发后重置计数器
    - after_agent 兜底：对话结束时若有未处理消息也触发一次

    注意事项：
    - 记忆提取是异步后台任务，不阻塞主对话流
    - 需要 user_id 才能正确关联记忆；解析不到 user_id 时跳过（仅告警）
    - 如果 MemoryPipeline 未配置 extractor，会静默跳过
    """

    state_schema = MemoryUpdateState  # type: ignore[assignment]

    def __init__(
        self,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        trigger_tokens: int = 100_000,
    ):
        """
        初始化记忆更新中间件

        Args:
            user_id: 用户 ID。传入时直接使用（per-user 实例）；为 None 时在
                共享 graph 下从 RunnableConfig.configurable 运行时解析。
            thread_id: 对话线程 ID。为 None 时优先取 runtime.execution_info.thread_id，
                再回退到 configurable.thread_id。
            trigger_tokens: 触发记忆更新的 token 阈值（默认 100K）
        """
        super().__init__()
        self.user_id = user_id
        self.thread_id = thread_id
        self.trigger_tokens = trigger_tokens

        # 以 user_id 为键的防重入集合 + 后台任务引用。
        # 共享 graph 下所有 run 复用同一中间件实例，per-user 键保证并发用户互不干扰。
        self._processing_users: set[str] = set()
        self._memory_tasks: dict[str, asyncio.Task] = {}

    def _resolve_ids(self, runtime: Runtime) -> tuple[Optional[str], Optional[str]]:
        """
        解析当前 run 的 user_id / thread_id。

        优先用实例属性（per-user 模式）；为 None 时从 RunnableConfig.configurable
        解析（共享 graph 模式），thread_id 再回退到 runtime.execution_info.thread_id。

        解析失败（如开发环境无 configurable）时对应值为 None，
        调用方应据此跳过记忆提取。
        """
        uid = self.user_id
        tid = self.thread_id

        if uid is None or tid is None:
            try:
                from langgraph.config import get_config

                cfg = get_config() or {}
                conf = cfg.get("configurable") or {}
                if uid is None:
                    uid = conf.get("user_id")
                if tid is None:
                    tid = conf.get("thread_id")
            except Exception:
                pass

        if tid is None:
            info = getattr(runtime, "execution_info", None)
            tid = getattr(info, "thread_id", None)

        return uid, tid

    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Agent 开始前记录解析出的身份（计数器由 UntrackedValue 随 run 重置）"""
        uid, tid = self._resolve_ids(runtime)
        logger.info(
            f"[MemoryUpdate] Started | trigger_tokens={self.trigger_tokens} | "
            f"user={uid[:8] if uid else '(unresolved)'} | "
            f"thread={tid[:8] if tid else '(unresolved)'}"
        )
        return None

    def after_model(self, state: MemoryUpdateState, runtime: Runtime) -> dict[str, Any] | None:
        """
        每次 LLM 调用后检查 token 使用量

        当累计 token 超过阈值时，触发异步记忆提取。
        """
        messages = state.get("messages", [])
        total_tokens = 0
        if messages:
            last = messages[-1]
            usage = getattr(last, "usage_metadata", None) or {}
            total_tokens = usage.get("total_tokens", 0)

        accumulated = state.get("memory_accumulated_tokens", 0) + total_tokens
        since_update = state.get("memory_messages_since_update", 0) + 1

        updates: dict[str, Any] = {
            "memory_accumulated_tokens": accumulated,
            "memory_messages_since_update": since_update,
        }

        # 检查是否达到触发阈值
        if accumulated >= self.trigger_tokens:
            uid, tid = self._resolve_ids(runtime)
            if uid is None:
                logger.warning(
                    f"[MemoryUpdate] Trigger reached but user_id unresolved; "
                    f"skipping extraction | tokens={accumulated}/{self.trigger_tokens} "
                    f"| messages={since_update}"
                )
            else:
                logger.info(
                    f"[MemoryUpdate] Trigger threshold reached: "
                    f"{accumulated}/{self.trigger_tokens} tokens | "
                    f"user={uid[:8]} | messages={since_update}"
                )
                self._trigger_memory_extraction(state, uid, tid)
            # 无论是否提取（或因防重入跳过），本轮计数已计入，重置等待下一轮
            updates["memory_accumulated_tokens"] = 0
            updates["memory_messages_since_update"] = 0

        return updates

    async def aafter_model(
        self, state: MemoryUpdateState, runtime: Runtime
    ) -> dict[str, Any] | None:
        return self.after_model(state, runtime)

    def after_agent(self, state: MemoryUpdateState, runtime: Runtime) -> dict[str, Any] | None:
        """
        Agent 结束后，如果有未处理的对话也触发记忆提取

        确保即使未达到 token 阈值，对话结束时也能提取记忆。
        """
        since_update = state.get("memory_messages_since_update", 0)
        accumulated = state.get("memory_accumulated_tokens", 0)
        logger.info(
            f"[MemoryUpdate] Agent ended | "
            f"accumulated_tokens={accumulated}/{self.trigger_tokens} | "
            f"messages_since_update={since_update}"
        )
        # 如果有消息积累但未触发过，在对话结束时也处理
        if since_update > 0:
            uid, tid = self._resolve_ids(runtime)
            if uid is None:
                logger.warning(
                    f"[MemoryUpdate] Agent ended but user_id unresolved; "
                    f"skipping extraction | messages={since_update}"
                )
            else:
                self._trigger_memory_extraction(state, uid, tid)
            return {"memory_accumulated_tokens": 0, "memory_messages_since_update": 0}
        return None

    def _trigger_memory_extraction(
        self, state: AgentState, user_id: str, thread_id: Optional[str]
    ) -> None:
        """
        触发异步记忆提取

        在后台运行，不阻塞主对话流。以 user_id 为键防重入，后台任务完成时
        在 done_callback 中清理键。
        """
        if user_id in self._processing_users:
            logger.debug(f"[MemoryUpdate] Already processing user={user_id[:8]}; skip")
            return

        messages = state.get("messages", [])
        if not messages:
            return

        self._processing_users.add(user_id)
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(self._extract_memories(messages, user_id, thread_id))
            # 持有 task 引用防 GC，done_callback 按 user_id 清理防重入键
            self._memory_tasks[user_id] = task
            task.add_done_callback(lambda t, uid=user_id: self._on_extraction_done(t, uid))
        except RuntimeError:
            # agent 始终在事件循环内执行，正常不会走到这里；
            # 不再使用 asyncio.run（在运行中的事件循环内会抛 RuntimeError）
            self._processing_users.discard(user_id)
            self._memory_tasks.pop(user_id, None)
            logger.warning("[MemoryUpdate] No running event loop; skipping extraction")

    def _on_extraction_done(self, task: asyncio.Task, user_id: str) -> None:
        """后台任务完成回调：按 user_id 清理防重入键并记录异常"""
        self._processing_users.discard(user_id)
        self._memory_tasks.pop(user_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"[MemoryUpdate] Background extraction task failed: {exc}")

    async def _extract_memories(
        self, messages: list, user_id: str, thread_id: Optional[str]
    ) -> None:
        """
        执行记忆提取

        使用 MemoryPipeline 处理对话消息，提取并存储记忆。
        """
        try:
            from src.agents.harness.runtime.memory.pipeline import get_memory_pipeline

            pipeline = get_memory_pipeline()

            # 检查 pipeline 是否配置了 extractor
            if pipeline.extractor is None:
                logger.debug("[MemoryUpdate] No extractor configured, skipping")
                return

            stats = await pipeline.process_conversation(
                user_id=user_id,
                messages=messages,
                thread_id=thread_id,
            )

            logger.info(
                f"[MemoryUpdate] Memory extraction completed | "
                f"user={user_id[:8]} | "
                f"episodic={stats.get('episodic', 0)} | "
                f"semantic={stats.get('semantic', 0)} | "
                f"procedural={stats.get('procedural', 0)}"
            )

            # 提取后整合（合并重复 + LLM 升华），best-effort，失败不影响提取结果
            try:
                cons_stats = await pipeline.consolidate_memories(user_id)
                logger.info(
                    f"[MemoryUpdate] Consolidation done | "
                    f"user={user_id[:8]} | "
                    f"merged={cons_stats.get('merged', 0)} | "
                    f"insights={cons_stats.get('insights', 0)}"
                )
            except Exception as ce:
                logger.warning(f"[MemoryUpdate] Consolidation skipped: {ce}")

        except ImportError as e:
            logger.warning(f"[MemoryUpdate] Memory module not available: {e}")
        except Exception as e:
            logger.error(f"[MemoryUpdate] Memory extraction failed: {e}")


def create_memory_update_middleware(
    user_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    trigger_tokens: int = 100_000,
) -> MemoryUpdateMiddleware:
    """
    工厂函数：创建记忆更新中间件

    Args:
        user_id: 用户 ID（per-user 模式传入；共享 graph 模式留空运行时解析）
        thread_id: 对话线程 ID
        trigger_tokens: 触发阈值（默认 100K）

    Returns:
        MemoryUpdateMiddleware 实例
    """
    return MemoryUpdateMiddleware(
        user_id=user_id,
        thread_id=thread_id,
        trigger_tokens=trigger_tokens,
    )
