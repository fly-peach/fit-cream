"""
FitCream 会话压缩 + 记忆提炼中间件（子类化 LangChain 内置 SummarizationMiddleware）

一个中间件承载一个完整流程（D3 记忆提炼彻底跟压缩走）：
    模型调用前判定输入 token 达阈值 -> 生成健身域结构化摘要 -> 替换历史
    （RemoveMessage + 重注入 system + 摘要占位 + 保留尾条）-> 用摘要文本后台提炼记忆
    （MemoryPipeline 写回三层）。压缩与记忆提炼同触发点、同模块，不再拆分。

替代自研 StructuredSummarizationMiddleware（2026-08-29 计划）：
- D2 压缩阈值动态化：默认 150K，plan_design 会话 200K（按 configurable.plan_design 运行时解析）
- D9 触发判定用真实 usage_metadata.input_tokens（对齐旧 _last_input_tokens），
  无 usage / 非数值时回退 count_tokens_approximately
- D4 摘要格式：健身域 7 节 STRUCTURED_SUMMARY_PROMPT；失败 raise（不塞 Error 摘要），
  由 @state_hook_fail_open 语义 = 保留原消息、下次再触发
- D8 压缩 RemoveMessage(ALL) 后重注入 agent.md（BASE_SYSTEM_PROMPT）SystemMessage，
  与 create_agent 首条 SystemMessage 一致（含 skills catalog 时由构造方传入）
- thrash 防护：压缩后清空保留消息的陈旧 usage_metadata（input_tokens/total_tokens），
  下一轮 _real_input_tokens 读到空 usage 回退近似估算（压缩后消息量小，不再重复触发）
- D3/D7 记忆提炼：摘要生成成功后，用摘要文本跑 MemoryPipeline 提炼并写回
  MemoryStore 三层（后台任务，防重入，lifespan shutdown 经 get_shared_memory_middleware
  排空，见 agent_graph.shutdown_agent）
"""

import asyncio
import logging
from typing import Any, Optional

from langchain.agents.middleware.summarization import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
)
from langchain_core.messages.utils import (
    count_tokens_approximately,
    get_buffer_string,
    trim_messages,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime

from src.agents.harness.orchestration.model_factory import resolve_chat_model
from src.agents.harness.orchestration.prompts.system import SYSTEM_PROMPT
from src.agents.harness.runtime.config_flags import get_config_flag, get_config_value
from src.agents.harness.runtime.middleware.robust import state_hook_fail_open

logger = logging.getLogger("fitcream.agent")

# D2 压缩触发阈值：默认 150K，plan_design 会话 200K（单一来源，agent_factory / callbacks 复用）
SUMMARIZE_TRIGGER_TOKENS = 150_000
PLAN_DESIGN_TRIGGER_TOKENS = 200_000

# trim_messages 异常兜底：保留最近 15 条
_SUMMARY_FALLBACK_MESSAGES = 15

# 共享中间件实例（lifespan shutdown 排空后台记忆提炼任务，见 agent_graph.shutdown_agent）
_shared_middleware: Optional["FitCreamSummarizationMiddleware"] = None


def get_shared_memory_middleware() -> Optional["FitCreamSummarizationMiddleware"]:
    """获取共享中间件实例（生产 graph 最后一次构造的实例）。

    压缩与记忆提炼在同一中间件内（D3），shutdown() 排空其中挂起的记忆提炼任务，
    agent_graph.shutdown_agent 依赖此入口。
    """
    return _shared_middleware

# D4 健身域结构化摘要提示词（7 节，含「待办队列进度」）
STRUCTURED_SUMMARY_PROMPT = """<role>
健身教练会话上下文提取助手
</role>

<primary_objective>
提取对话历史中最重要的上下文，用于替换即将超过上下文窗口的旧消息。
</primary_objective>

<instructions>
你正在接近单次可接受的输入 token 上限。请把下面的对话历史合并为一份结构化摘要，
保留所有值得长期记住的信息（已完成的动作不要重复，重点是继续推进所需的关键上下文）。

请严格使用以下小节组织输出（健身领域）。每节都必须填写：有内容则写内容，无内容则写 "无"：

## 用户目标
用户的健身目标（减脂/增肌/维持/改善健康）及任何阶段性调整。

## 身体数据
身高、体重、年龄、体脂率等已知身体数据及其变化。

## 活跃计划
当前生效的训练/饮食计划要点（哪天练什么、组次重量、饮食结构）。

## 训练与饮食进度
训练打卡、饮食记录、统计进展、连续打卡 streak 等进度信息。

## 偏好与伤病
用户偏好（器械、时段、动作）、伤病与禁忌、需要避免的内容。

## 待办队列进度
若存在计划设计（plan-creation）流程的待办队列，记录队列标题、已完成项、
当前推进项、下一步该做什么；无队列则写 "无"。

## 下一步
接下来应推进的具体事项。

只输出这份摘要本身，不要输出任何额外说明或前后缀。

<messages>
对话历史：
{messages}
</messages>"""  # noqa: E501


class FitCreamSummarizationMiddleware(SummarizationMiddleware):
    """FitCream 会话压缩 + 记忆提炼中间件（内置 SummarizationMiddleware 子类）。

    与内置的差异：
    - 触发阈值动态化（150K / plan_design 200K），绕过内置 reported-tokens 的
      provider 匹配限制（自定义 _should_summarize）
    - 触发判定基于真实 input_tokens（_real_input_tokens），非近似估算
    - 摘要模型按 configurable.deepseek_api_key 路由（有 key 走 deepseek，否则 qwen）
    - 摘要失败 raise -> state_hook_fail_open 保留原消息
    - 压缩后重注入系统提示词 SystemMessage + 清空保留消息陈旧 usage
    - 压缩成功后触发后台记忆提炼（D3，同一中间件内：用摘要文本写回三层）
    """

    def __init__(
        self,
        model,
        *,
        system_prompt: Optional[str] = None,
        keep_messages: int = 10,
        summary_prompt: str = STRUCTURED_SUMMARY_PROMPT,
        token_counter=None,
    ) -> None:
        self.system_prompt = system_prompt or SYSTEM_PROMPT
        super().__init__(
            model=model,
            trigger=None,
            keep=("messages", keep_messages),
            summary_prompt=summary_prompt,
            token_counter=token_counter or self._real_input_tokens,
        )
        # D3 记忆提炼后台任务：以 user_id 为键防重入 + 任务引用（shutdown 排空）。
        # 共享 graph 下所有 run 复用同一中间件实例，per-user 键保证并发用户互不干扰。
        self._processing_users: set[str] = set()
        self._refinement_tasks: dict[str, asyncio.Task] = {}

        # 注册为共享实例（agent_graph.shutdown_agent 据此排空后台记忆任务）
        global _shared_middleware
        _shared_middleware = self

    # ===== 触发判定（D2 / D9） =====

    def _threshold(self) -> int:
        """压缩阈值：plan_design 会话 200K，其余 150K（D2）。"""
        if get_config_flag("plan_design"):
            return PLAN_DESIGN_TRIGGER_TOKENS
        return SUMMARIZE_TRIGGER_TOKENS

    def _should_summarize(self, messages: list[AnyMessage], total_tokens: int) -> bool:
        """彻底绕过内置 _should_summarize_based_on_reported_tokens 的 provider 匹配限制。"""
        return total_tokens >= self._threshold()

    @staticmethod
    def _real_input_tokens(messages: list[AnyMessage]) -> int:
        """取最近一次模型调用的真实 input_tokens（真实上下文大小）。

        count_tokens_approximately（len//4）对中文/JSON 工具输出严重低估，
        导致真实 198k 上下文的线程不触发压缩。AIMessage.usage_metadata.input_tokens
        随 checkpoint 持久化，新 run 首轮 before_model 即可读到上次上下文大小。
        解析失败/非数值回退近似估算（首轮 / 模型未回传 usage / 压缩后 sanitize 场景）。
        """
        for msg in reversed(messages):
            if not isinstance(msg, AIMessage):
                continue
            usage = getattr(msg, "usage_metadata", None) or {}
            raw = usage.get("input_tokens") or 0
            tokens = int(raw) if isinstance(raw, (int, float)) else 0
            if tokens > 0:
                return tokens
        try:
            return int(count_tokens_approximately(messages))
        except Exception:
            return 0

    # ===== 摘要生成（D4 / D6） =====

    def _resolve_summary_model(self):
        """按 configurable.deepseek_api_key 解析摘要模型（D6 路由）。

        有用户 DS key 走 deepseek（压缩关思考），否则用构造传入的 qwen 摘要模型。
        """
        key = get_config_value("deepseek_api_key")
        if isinstance(key, str) and key.strip():
            return resolve_chat_model(user_ds_key=key.strip(), enable_thinking=False)
        return self.model

    def _trim_messages_for_summary(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        """裁剪待摘要消息到 token 上限。

        不用 self.token_counter（真实 usage 口径）做 trim，避免触发消息携带的超大
        input_tokens 使 trim_messages 误判；统一用近似估算。
        """
        try:
            if self.trim_tokens_to_summarize is None:
                return messages
            return trim_messages(
                messages,
                max_tokens=self.trim_tokens_to_summarize,
                token_counter=count_tokens_approximately,
                start_on="human",
                strategy="last",
                allow_partial=True,
                include_system=True,
            )
        except Exception:
            return messages[-_SUMMARY_FALLBACK_MESSAGES:]

    def _create_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """同步生成摘要；失败 raise（fail-open 保留原消息，D4）。"""
        if not messages_to_summarize:
            return "无"
        trimmed = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed:
            return "无"
        formatted = get_buffer_string(trimmed, format="xml")
        model = self._resolve_summary_model()
        try:
            response = model.invoke(
                self.summary_prompt.format(messages=formatted).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
        except Exception as e:
            logger.warning("[Summarization] 摘要生成失败，保留原消息: %s", e)
            raise
        summary = response.text.strip()
        self._schedule_memory_refinement(summary)
        return summary

    async def _acreate_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        """异步生成摘要；失败 raise（fail-open 保留原消息，D4）。"""
        if not messages_to_summarize:
            return "无"
        trimmed = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed:
            return "无"
        formatted = get_buffer_string(trimmed, format="xml")
        model = self._resolve_summary_model()
        try:
            response = await model.ainvoke(
                self.summary_prompt.format(messages=formatted).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
        except Exception as e:
            logger.warning("[Summarization] 摘要生成失败，保留原消息: %s", e)
            raise
        summary = response.text.strip()
        self._schedule_memory_refinement(summary)
        return summary

    # ===== thrash 防护（任务 4） =====

    @staticmethod
    def _sanitize_preserved_usage(preserved: list[AnyMessage]) -> None:
        """压缩后清空保留消息携带的陈旧 usage_metadata。

        压缩前的超大 input_tokens 若残留在保留消息上，下一轮 before_model 会
        误判上下文仍超限、每轮重复压缩（thrash）。清空后 _real_input_tokens
        回退到近似估算（对压缩后的小上下文不会再触发）。
        """
        for msg in preserved:
            if isinstance(msg, AIMessage):
                usage = getattr(msg, "usage_metadata", None)
                if isinstance(usage, dict):
                    usage.pop("input_tokens", None)
                    usage.pop("total_tokens", None)

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        """把摘要包装为占位 HumanMessage（lc_source=summarization，供后续识别）。"""
        return [
            HumanMessage(
                content=f"以下是截至目前的对话摘要：\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]

    # ===== 记忆提炼（D3：跟压缩走，后台任务写回 MemoryStore 三层） =====

    def _schedule_memory_refinement(self, summary: str) -> None:
        """摘要生成成功后调度后台记忆提炼（best-effort，不阻塞压缩）。

        以 user_id 为键防重入；后台任务在 done_callback 中按 user_id 清理。
        """
        user_id = get_config_value("user_id")
        if not user_id:
            logger.debug("[Summarization] 无 user_id，跳过压缩后记忆提炼")
            return
        uid = str(user_id)
        if uid in self._processing_users:
            logger.debug(f"[Summarization] 记忆提炼进行中 user={uid[:8]}; skip")
            return
        if not summary or not summary.strip():
            return
        thread_id = get_config_value("thread_id")
        tid = str(thread_id) if thread_id else None

        self._processing_users.add(uid)
        try:
            loop = asyncio.get_running_loop()
            # 决策 Q2/D6：记忆提炼「本次请求带 DS key 就用用户 deepseek，否则 qwen」。
            # 在 create_task 前解析（ContextVar 随任务继承有边界情况），显式传入后台任务。
            ds_llm = self._resolve_ds_llm()
            task = loop.create_task(
                self._refine_from_summary(summary, uid, tid, ds_llm)
            )
            # 持有 task 引用防 GC，done_callback 按 user_id 清理防重入键
            self._refinement_tasks[uid] = task
            task.add_done_callback(lambda t, u=uid: self._on_refinement_done(t, u))
        except RuntimeError:
            # agent 始终在事件循环内执行，正常不会走到这里；
            # 不再使用 asyncio.run（在运行中的事件循环内会抛 RuntimeError）
            self._processing_users.discard(uid)
            self._refinement_tasks.pop(uid, None)
            logger.warning("[Summarization] 无事件循环，跳过压缩后记忆提炼")

    @staticmethod
    def _resolve_ds_llm() -> Optional[BaseChatModel]:
        """按当前 run 的 configurable.deepseek_api_key 解析记忆提炼模型。

        带 key 时用用户 deepseek（缓存复用）；否则 None（走全局 extractor_llm）。
        记忆提炼不需要思考，统一关思考省 reasoning tokens。
        """
        key = get_config_value("deepseek_api_key")
        if isinstance(key, str) and key.strip():
            return resolve_chat_model(user_ds_key=key.strip(), enable_thinking=False)
        return None

    def _on_refinement_done(self, task: asyncio.Task, user_id: str) -> None:
        """后台任务完成回调：按 user_id 清理防重入键并记录异常。"""
        self._processing_users.discard(user_id)
        self._refinement_tasks.pop(user_id, None)
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error(f"[Summarization] 记忆提炼后台任务失败: {exc}")

    async def _refine_from_summary(
        self,
        summary: str,
        user_id: str,
        thread_id: Optional[str],
        llm: Optional[BaseChatModel] = None,
    ) -> None:
        """用摘要文本执行记忆提炼：MemoryPipeline 提取 + 整合，写回三层。"""
        try:
            from src.agents.harness.runtime.memory.pipeline import get_memory_pipeline

            pipeline = get_memory_pipeline()

            # 检查 pipeline 是否配置了 extractor
            if pipeline.extractor is None:
                logger.debug("[Summarization] 记忆提炼：无 extractor 配置，跳过")
                return

            # 提炼输入为摘要文本（单一 HumanMessage），口径与旧对话级提炼一致
            messages = [HumanMessage(content=summary)]
            stats = await pipeline.process_conversation(
                user_id=user_id,
                messages=messages,
                thread_id=thread_id,
                llm=llm,
            )

            logger.info(
                f"[Summarization] 记忆提炼完成 | user={user_id[:8]} | "
                f"episodic={stats.get('episodic', 0)} | "
                f"semantic={stats.get('semantic', 0)} | "
                f"procedural={stats.get('procedural', 0)}"
            )

            # 提取后整合（合并重复 + LLM 升华），best-effort，失败不影响提取结果
            try:
                cons_stats = await pipeline.consolidate_memories(user_id, llm=llm)
                logger.info(
                    f"[Summarization] 记忆整合完成 | user={user_id[:8]} | "
                    f"merged={cons_stats.get('merged', 0)} | "
                    f"insights={cons_stats.get('insights', 0)}"
                )
            except Exception as ce:
                logger.warning(f"[Summarization] 记忆整合跳过: {ce}")

        except ImportError as e:
            logger.warning(f"[Summarization] 记忆模块不可用: {e}")
        except Exception as e:
            logger.error(f"[Summarization] 记忆提炼失败: {e}")

    async def shutdown(self) -> None:
        """排空/取消进行中的后台记忆提炼任务，防止其持有 DB 连接跨事件循环存活。

        lifespan shutdown 时调用（agent_graph.shutdown_agent）：取消未完成的任务
        并等待其收尾（连接归还池），避免 AsyncAdaptedQueuePool 的 GC 清理告警
        （non-checked-in connection）。
        """
        tasks = list(self._refinement_tasks.values())
        self._refinement_tasks.clear()
        self._processing_users.clear()
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ===== before_model / abefore_model（D8 重注入 system） =====

    @state_hook_fail_open
    def before_model(
        self, state: Any, runtime: Runtime
    ) -> Optional[dict[str, Any]]:
        """模型调用前触发压缩（同步路径）。"""
        messages = state.get("messages", [])
        self._ensure_message_ids(messages)

        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None

        cutoff = self._determine_cutoff_index(messages)
        if cutoff <= 0:
            return None

        to_summarize, preserved = self._partition_messages(messages, cutoff)
        summary = self._create_summary(to_summarize)
        # thrash 防护：压缩后清空保留消息的陈旧 usage，下一轮不再误触发
        self._sanitize_preserved_usage(preserved)

        logger.info(
            f"[Summarization] 触发压缩 | 压缩 {len(to_summarize)} 条 | "
            f"保留 {len(preserved)} 条 | tokens={total_tokens}"
        )

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=self.system_prompt),
                *self._build_new_messages(summary),
                *preserved,
            ]
        }

    @state_hook_fail_open
    async def abefore_model(
        self, state: Any, runtime: Runtime
    ) -> Optional[dict[str, Any]]:
        """模型调用前触发压缩（异步路径，生产 SSE 走这里）。"""
        messages = state.get("messages", [])
        self._ensure_message_ids(messages)

        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None

        cutoff = self._determine_cutoff_index(messages)
        if cutoff <= 0:
            return None

        to_summarize, preserved = self._partition_messages(messages, cutoff)
        summary = await self._acreate_summary(to_summarize)
        # thrash 防护：压缩后清空保留消息的陈旧 usage，下一轮不再误触发
        self._sanitize_preserved_usage(preserved)

        logger.info(
            f"[Summarization] 触发压缩 | 压缩 {len(to_summarize)} 条 | "
            f"保留 {len(preserved)} 条 | tokens={total_tokens}"
        )

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                SystemMessage(content=self.system_prompt),
                *self._build_new_messages(summary),
                *preserved,
            ]
        }
