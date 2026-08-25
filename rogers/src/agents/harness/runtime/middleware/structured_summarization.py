"""
结构化增量会话压缩中间件（替换内置 SummarizationMiddleware）

触发条件：同一 thread 累积消息 token 数超过 trigger_tokens（沿用
SUMMARIZE_TRIGGER_TOKENS=100_000）。防上下文溢出。

摘要格式：健身域结构化 markdown：
    ## 用户目标 / ## 身体数据 / ## 活跃计划 / ## 训练与饮食进度 /
    ## 偏好与伤病 / ## 待办队列进度 / ## 下一步

增量更新：首次触发从全量历史生成摘要；后续触发把「上一份摘要 + 新增消息」
合并为更新版，而不是重写全历史，避免上下文在反复压缩中丢失。

持久化：摘要写入 state_schema 的持久化私有通道 conversation_summary
（``Annotated[str, PrivateStateAttr]``，随 checkpoint 存 Postgres，跨 run 存活；
注意区别于 ``UntrackedValue``——后者随 run 重置，无法承载跨 run 摘要）。

消息替换：把 keep 尾条之前的消息替换为新的摘要消息（HumanMessage，
lc_source=summarization），保留最近 keep_messages 条消息保证上下文连贯。

与 thread_usages（覆盖式「最近一次调用上下文大小」）正交：压缩只在模型输入层
替换历史，chat.py 的 usage/usage_total 与前端进度条语义不受影响。
"""

import logging
import uuid
from typing import Annotated, Any, Callable, Optional

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import PrivateStateAttr
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately, get_buffer_string
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from src.agents.harness.runtime.config_flags import get_config_value

logger = logging.getLogger("fitcream.agent")

TokenCounter = Callable[[list], int]

# 增量摘要提示词：保留上一份摘要 + 合并新增消息，输出健身域结构化 markdown
STRUCTURED_SUMMARY_PROMPT = """<role>
健身教练会话上下文提取助手
</role>

<primary_objective>
提取/更新对话历史中最重要的上下文，用于替换即将超过上下文窗口的旧消息。
</primary_objective>

<instructions>
你正在接近单次可接受的输入 token 上限。请把下面的「现有摘要」与「新增对话」合并为
一份更新后的摘要。更新时必须**保留现有摘要中的所有信息**（除非被新增对话明确推翻），
再把新增对话中值得长期记住的内容补充进去。

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

只输出这份更新后的摘要本身，不要输出任何额外说明或前后缀。

<existing_summary>
{summary}
</existing_summary>

<messages>
新增对话：
{messages}
</messages>"""  # noqa: E501


def _is_summary_message(message: AnyMessage) -> bool:
    """判断消息是否为历史压缩产生的摘要占位消息（避免增量时重复喂入）。"""
    return (
        isinstance(message, HumanMessage)
        and message.additional_kwargs.get("lc_source") == "summarization"
    )


class StructuredSummarizationState(AgentState):
    """压缩中间件的状态通道。

    conversation_summary 为持久化私有通道：随 checkpoint 存 Postgres、跨 run
    存活、不对模型可见（PrivateStateAttr）。区别于 UntrackedValue（随 run 重置）。
    """

    conversation_summary: NotRequired[Annotated[str, PrivateStateAttr]]


class StructuredSummarizationMiddleware(AgentMiddleware):
    """
    结构化增量会话压缩中间件（替换内置 SummarizationMiddleware）。

    用法与内置一致，但：
    - 摘要为健身域结构化 markdown（含待办队列进度）
    - 二次触发为增量更新（保留旧摘要 + 合并新消息），非全量重写
    - 摘要持久化在 conversation_summary 通道，跨 run 存活
    """

    state_schema = StructuredSummarizationState  # type: ignore[assignment]

    def __init__(
        self,
        model: BaseChatModel,
        *,
        trigger_tokens: int = 100_000,
        keep_messages: int = 10,
        token_counter: TokenCounter = count_tokens_approximately,
        summary_prompt: str = STRUCTURED_SUMMARY_PROMPT,
        model_resolver: Optional[Callable[..., BaseChatModel]] = None,
    ) -> None:
        super().__init__()
        self.model = model
        self.trigger_tokens = trigger_tokens
        self.keep_messages = keep_messages
        self.token_counter = token_counter
        self.summary_prompt = summary_prompt
        # 可选模型解析器：有用户 DeepSeek key 时（决策 Q2 会话压缩走用户 deepseek）
        # 用该 resolver 解析模型；无 key 时回退 self.model（qwen）。签名
        # ``model_resolver(*, user_ds_key=None) -> BaseChatModel``。
        self.model_resolver = model_resolver

    def _resolve_model(self) -> BaseChatModel:
        """按当前 run 的 configurable.deepseek_api_key 解析摘要模型。"""
        if self.model_resolver is not None:
            key = get_config_value("deepseek_api_key")
            if isinstance(key, str) and key.strip():
                return self.model_resolver(user_ds_key=key.strip())
        return self.model

    @staticmethod
    def _ensure_message_ids(messages: list[AnyMessage]) -> None:
        """为消息补齐唯一 id，供 add_messages reducer 按 id 替换/删除。"""
        for msg in messages:
            if msg.id is None:
                msg.id = str(uuid.uuid4())

    def _find_safe_cutoff(self, messages: list[AnyMessage]) -> int:
        """确定裁剪点：从尾部保留 keep_messages 条，且不拆散 AI/Tool 成对消息。

        返回需要被压缩（替换）的消息数；<=0 表示无需压缩。
        """
        if len(messages) <= self.keep_messages:
            return 0
        target_cutoff = len(messages) - self.keep_messages
        cutoff = target_cutoff
        # 若裁剪点落在 ToolMessage 上，向前找到包含对应 tool_calls 的 AIMessage
        while cutoff < len(messages) and isinstance(messages[cutoff], ToolMessage):
            tool_call_ids = {
                m.tool_call_id
                for m in messages[cutoff:]
                if isinstance(m, ToolMessage) and m.tool_call_id
            }
            found = None
            for i in range(cutoff - 1, -1, -1):
                msg = messages[i]
                if isinstance(msg, AIMessage) and msg.tool_calls:
                    ai_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}
                    if tool_call_ids & ai_ids:
                        found = i
                        break
            if found is not None:
                cutoff = found
                break
            # 无匹配 AIMessage：越过这些 ToolMessage
            idx = cutoff
            while idx < len(messages) and isinstance(messages[idx], ToolMessage):
                idx += 1
            cutoff = idx
            break
        return cutoff

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        """把摘要包装为占位 HumanMessage（lc_source=summarization，供后续增量识别）。"""
        return [
            HumanMessage(
                content=f"以下是截至目前的对话摘要：\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]

    def _prepare_prompt(self, messages_to_summarize: list[AnyMessage], prev_summary: str) -> str:
        """组装增量摘要提示词：过滤旧摘要占位消息，避免重复喂入。"""
        fresh = [m for m in messages_to_summarize if not _is_summary_message(m)]
        formatted = get_buffer_string(fresh, format="xml") if fresh else "（无新增对话）"
        return self.summary_prompt.format(summary=prev_summary or "（无，首次生成）", messages=formatted).rstrip()

    def _create_summary(
        self, messages_to_summarize: list[AnyMessage], prev_summary: str
    ) -> str:
        """同步生成增量摘要。"""
        try:
            model = self._resolve_model()
            response = model.invoke(
                self._prepare_prompt(messages_to_summarize, prev_summary),
                config={"metadata": {"lc_source": "summarization"}},
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("[Summarization] 摘要生成失败，保留原消息: %s", e)
            raise

    async def _acreate_summary(
        self, messages_to_summarize: list[AnyMessage], prev_summary: str
    ) -> str:
        """异步生成增量摘要。"""
        try:
            model = self._resolve_model()
            response = await model.ainvoke(
                self._prepare_prompt(messages_to_summarize, prev_summary),
                config={"metadata": {"lc_source": "summarization"}},
            )
            return response.text.strip()
        except Exception as e:
            logger.warning("[Summarization] 摘要生成失败，保留原消息: %s", e)
            raise

    def _summarize_plan(
        self, state: StructuredSummarizationState
    ) -> Optional[tuple[list[AnyMessage], list[AnyMessage], str, int]]:
        """压缩判定与分区（同步/异步共用）：返回
        ``(to_summarize, preserved, prev_summary, total_tokens)``，无需压缩返回 None。"""
        messages = state.get("messages", [])
        if not messages:
            return None

        self._ensure_message_ids(messages)

        try:
            total_tokens = self.token_counter(messages)
        except Exception:
            total_tokens = 0

        if total_tokens < self.trigger_tokens:
            return None

        cutoff = self._find_safe_cutoff(messages)
        if cutoff <= 0:
            return None

        return (
            messages[:cutoff],
            messages[cutoff:],
            state.get("conversation_summary") or "",
            total_tokens,
        )

    def before_model(
        self, state: StructuredSummarizationState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """模型调用前触发压缩（同步路径）。"""
        plan = self._summarize_plan(state)
        if plan is None:
            return None
        to_summarize, preserved, prev_summary, total_tokens = plan

        logger.info(
            f"[Summarization] 触发结构化增量压缩 | 压缩 {len(to_summarize)} 条 "
            f"| 保留 {len(preserved)} 条 | tokens={total_tokens}"
        )

        try:
            summary = self._create_summary(to_summarize, prev_summary)
        except Exception as e:
            # 压缩失败不阻断对话：返回 None 保留原消息，下次再触发
            logger.warning("[Summarization] 压缩中断，保留原消息: %s", e)
            return None

        new_messages = self._build_new_messages(summary)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved,
            ],
            "conversation_summary": summary,
        }

    async def abefore_model(
        self, state: StructuredSummarizationState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """模型调用前触发压缩（异步路径，生产 SSE 走这里）。"""
        plan = self._summarize_plan(state)
        if plan is None:
            return None
        to_summarize, preserved, prev_summary, total_tokens = plan

        logger.info(
            f"[Summarization] 触发结构化增量压缩 | 压缩 {len(to_summarize)} 条 "
            f"| 保留 {len(preserved)} 条 | tokens={total_tokens}"
        )

        try:
            summary = await self._acreate_summary(to_summarize, prev_summary)
        except Exception as e:
            logger.warning("[Summarization] 压缩中断，保留原消息: %s", e)
            return None

        new_messages = self._build_new_messages(summary)

        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved,
            ],
            "conversation_summary": summary,
        }
