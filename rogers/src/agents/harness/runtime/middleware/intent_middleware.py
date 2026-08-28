"""
意图识别中间件（渐进式提示词注入）

基于 LangChain AgentMiddleware 的 wrap_model_call hook（F1 迁移后为临时注入）：
1. 检测最新用户消息的意图（关键词多意图匹配 + 图片检测 + 可选 LLM 兜底）
2. 把命中的所有意图专项提示词临时合并进 request.system_message（不落 checkpoint）
3. 实现"渐进式披露"——仅注入与当前意图相关的规则

架构：
    用户消息 -> IntentMiddleware.wrap_model_call
                    |
                    v
              detect_intents(message)
                    |
            ┌───────┴──────────────┐
            |  图片检测   |  多意图关键词匹配  |  LLM 兜底（默认关）
            v            v                  v
      meal_image /  [plan_creation, checkin, ...]
      image_analysis
                    |
                    v
          注入 INTENT_PROMPTS[intent_1] + INTENT_PROMPTS[intent_2] + ...
          (合并进 request.system_message -> 临时、不持久化)

效果：
- 基础提示词始终存在（身份、能力概览、核心规则）
- 意图专项规则按需注入（减少 token，模型更聚焦）
- 每次用户新消息时重新检测意图
- 多意图按 INTENT_KEYWORDS 顺序（优先级）拼接注入，解决 plan_creation 的
  「计划」与 diet_record 的「饮食计划」等歧义——都命中就都注入，让模型自行取舍
- F1：注入走 wrap_model_call + system_message 合并，不再经 messages reducer
  持久化，长期线程不会逐轮累积 SystemMessage（token 膨胀 / 陈旧提示污染）

知识库耦合：knowledge_query 意图的注入需 KB 开关开启（configurable.kb_enabled），
该判断统一走 runtime/config_flags.get_config_flag，不再 import kb_gate_middleware
（消除中间件之间的跨模块耦合）。

LLM 兜底：默认关闭。仅当 configurable.intent_classify_llm 为真且关键词无任何
命中时才调用轻量分类模型，避免每轮用户消息都多一次 LLM 调用（延迟 + token）。
"""

import logging
from typing import Any, Optional

from langchain.agents.middleware import AgentMiddleware
from langchain.messages import HumanMessage

from src.agents.harness.orchestration.prompts.system import (
    INTENT_CLASSIFY_PROMPT,
    INTENT_KEYWORDS,
    INTENT_NEGATIVE_KEYWORDS,
    INTENT_PROMPTS,
    MEAL_IMAGE_KEYWORDS,
)
from src.agents.harness.runtime.config_flags import get_config_flag
from src.agents.harness.runtime.middleware.prompt_injection import merge_system_prompt

logger = logging.getLogger("fitcream.agent")

# 单轮最多注入的意图提示词数量（防止多个意图叠加失控）
MAX_INTENTS = 3

# 非 plan_design 会话中 plan_creation 的替代提示词键：完整计划设计（plan-execute）
# 流程只允许「为我设计健身计划」按钮进入的会话（configurable.plan_design）触发；
# 普通聊天里用户提及计划设计时，只注入「引导点击按钮」的轻量提示词。
PLAN_CREATION_BUTTON_INTENT = "plan_creation_button"


def _extract_text(content: Any) -> str:
    """从 HumanMessage.content 提取纯文本（支持 str / list 多模态块）。"""
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content) if content else ""


def detect_intents(message: HumanMessage) -> list[str]:
    """
    检测用户消息的有序意图列表（按优先级从高到低，最多 MAX_INTENTS 个）。

    检测策略：
    1. 图片检测：content 含 image_url 块 -> 伴随文本命中饮食关键词则
       meal_image_analysis，否则 image_analysis（图片意图独占）
    2. 多意图关键词匹配：遍历 INTENT_KEYWORDS，命中即加入（应用
       INTENT_NEGATIVE_KEYWORDS 负向关键词否决）
    3. 无命中：返回 ["general_chat"]

    Args:
        message: 用户消息（HumanMessage）

    Returns:
        意图名列表，如 ["plan_creation", "diet_record"] 或 ["image_analysis"]

    Example:
        >>> msg = HumanMessage(content="帮我制定减脂计划")
        >>> detect_intents(msg)
        ['plan_creation']

        >>> msg = HumanMessage(content="帮我记录饮食计划")
        >>> detect_intents(msg)
        ['plan_creation', 'diet_record']
    """
    content = message.content

    # 1. 图片检测（多模态消息，content 为 list）
    if isinstance(content, list):
        has_image = any(
            isinstance(block, dict) and block.get("type") == "image_url"
            for block in content
        )
        if has_image:
            text = _extract_text(content)
            # 伴随文本含饮食关键词 -> 饮食热量识别专项流程
            if any(kw in text for kw in MEAL_IMAGE_KEYWORDS):
                return ["meal_image_analysis"]
            return ["image_analysis"]

    # 2/3. 多意图关键词匹配 + 默认
    text = _extract_text(content)
    matched: list[str] = []
    for intent, keywords in INTENT_KEYWORDS.items():
        if not any(kw in text for kw in keywords):
            continue
        negatives = INTENT_NEGATIVE_KEYWORDS.get(intent, ())
        if any(nk in text for nk in negatives):
            continue
        matched.append(intent)
        if len(matched) >= MAX_INTENTS:
            break

    return matched if matched else ["general_chat"]


def detect_intent(message: HumanMessage) -> str:
    """向后兼容：返回最高优先级意图（detect_intents 的首个）。"""
    return detect_intents(message)[0]


class IntentMiddleware(AgentMiddleware):
    """
    意图识别中间件 - 渐进式提示词注入（多意图）。

    在 wrap_model_call 阶段（F1 临时注入）：
    1. 检查最新消息是否为用户消息（HumanMessage）
    2. 检测用户意图（图片检测 + 多意图关键词匹配 + 可选 LLM 兜底）
    3. 把命中的全部意图专项提示词临时合并进 request.system_message（不落 checkpoint）

    注入时机：仅在最新消息为 HumanMessage 时注入（即用户刚发送新消息时）。
    后续 model 调用（tool 执行后）不会重复注入，因为最新消息为 ToolMessage。

    Args:
        llm_classifier: 可选 LLM 兜底分类器（BaseChatModel 或 ``callable(text)->str``）。
            为 None 时即使 configurable.intent_classify_llm 开启也仅打日志跳过
            （不自动构造模型，避免默认引入额外调用开销）。

    无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
    """

    def __init__(self, llm_classifier: Optional[Any] = None):
        super().__init__()
        self.llm_classifier = llm_classifier

    def _classify_with_llm(self, text: str) -> Optional[str]:
        """用轻量分类模型兜底判断意图（仅关键词无命中且开关开启时调用）。"""
        classifier = self.llm_classifier
        if classifier is None:
            logger.info(
                "[Intent] intent_classify_llm 已开启但未配置 llm_classifier，跳过兜底"
            )
            return None

        try:
            if callable(classifier) and not hasattr(classifier, "ainvoke"):
                label = classifier(text)
            else:
                response = classifier.invoke(
                    INTENT_CLASSIFY_PROMPT.format(text=text[:2000])
                )
                label = response.text.strip() if hasattr(response, "text") else str(response)
            label = (label or "").strip().lower()
            if label in INTENT_KEYWORDS:
                return label
            logger.info("[Intent] LLM 兜底分类结果不可识别: %r", label)
        except Exception as e:
            logger.warning("[Intent] LLM 兜底分类失败: %s", e)
        return None

    def _compute_prompt(self, messages: list) -> Optional[str]:
        """计算本轮需要注入的意图提示词（无命中/门控拦截时返回 None）。

        语义与迁移前 before_model 一致：仅最新消息为 HumanMessage 时检测并注入，
        tool 循环（ToolMessage/AIMessage）不重复注入。
        """
        if not messages:
            return None

        last_msg = messages[-1]

        # 仅在用户发送新消息时注入（跳过 ToolMessage / AIMessage）
        if not isinstance(last_msg, HumanMessage):
            return None

        # 检测意图
        intents = detect_intents(last_msg)

        # LLM 兜底：默认关闭；仅当关键词无命中且开关开启时尝试分类
        if intents == ["general_chat"] and get_config_flag("intent_classify_llm", False):
            fallback = self._classify_with_llm(_extract_text(last_msg.content))
            if fallback:
                intents = [fallback]

        # plan_design 门控：完整计划设计（plan-execute）流程只允许按钮进入的
        # plan_design 会话（configurable.plan_design=true）触发。普通聊天里用户
        # 提及计划设计时，把 plan_creation 替换为「引导点击按钮」的轻量提示词，
        # 不进入队列/表单/大纲的完整流程。
        if "plan_creation" in intents and not get_config_flag("plan_design", False):
            intents = [
                PLAN_CREATION_BUTTON_INTENT if i == "plan_creation" else i
                for i in intents
            ]

        # knowledge_query 意图注入「优先知识库检索」引导，与 KB 工具门控矛盾：
        # 开关关闭（configurable.kb_enabled falsy）时跳过注入，避免模型想调不可见的 KB 工具。
        # 该判断经 runtime/config_flags.get_config_flag 统一读取，不跨中间件 import。
        if "knowledge_query" in intents and not get_config_flag("kb_enabled", False):
            intents = [i for i in intents if i != "knowledge_query"]
            if not intents:
                logger.info("[Intent] Detected: knowledge_query (skipped: KB disabled)")
                return None

        # 拼接所有命中意图的专项提示词（按优先级顺序）
        prompts = [INTENT_PROMPTS[i] for i in intents if INTENT_PROMPTS.get(i)]
        if not prompts:
            return None

        logger.info(f"[Intent] Detected: {intents}")

        # 多意图提示词合并为一个字符串，经 system_message 临时注入（不落 checkpoint）
        return "\n\n".join(prompts)

    def wrap_model_call(self, request, handler):
        """临时注入意图专项提示词（合并进 request.system_message，不持久化）。"""
        prompt = self._compute_prompt(request.messages)
        if not prompt:
            return handler(request)
        return handler(merge_system_prompt(request, prompt))

    async def awrap_model_call(self, request, handler):
        """异步路径（生产 SSE 走这里）：同 wrap_model_call。"""
        prompt = self._compute_prompt(request.messages)
        if not prompt:
            return await handler(request)
        return await handler(merge_system_prompt(request, prompt))
