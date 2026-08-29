"""
用户请求门控中间件（意图识别注入 + 知识库回答开关）

合并自 IntentMiddleware + KBGateMiddleware（2026-08-29）：两者本质是同一件事——
「按用户最新消息做门控」的 wrap_model_call 临时注入器：同一 hook（wrap_model_call /
awrap_model_call）、同一注入机制（merge_system_prompt，不落 checkpoint）、同一触发
条件（最新消息为 HumanMessage）、都读 configurable 开关。合并为一个中间件，门控
顺序见下。

职责：
1. 意图识别（渐进式披露）：检测最新用户消息意图（关键词多意图 + 图片检测 + 可选
   LLM 兜底），把命中的所有意图专项提示词临时合并进 request.system_message。
2. plan_design 门控：完整计划设计（plan-execute）流程只允许「设计计划」按钮进入的
   plan_design 会话（configurable.plan_design）触发；普通聊天里用户提及计划设计时，
   替换为「引导点击按钮」的轻量提示词。
3. 知识库回答开关（configurable.kb_enabled）：
   - 关闭：wrap_model_call 从 request.tools 移除 3 个 KB 工具（模型完全看不到）；
     同时跳过 knowledge_query 意图的注入（避免模型想调不可见的 KB 工具）。
   - 开启：注入 CONTEXT_PROMPTS["kb_answer"] 优先提示词（带站内出处链接）。

门控顺序（wrap_model_call 内）：
- 工具过滤（KB 关闭时移除 KB 工具）与提示词注入相互独立，先过滤再注入；
- 提示词拼接：意图提示词在前，KB 优先提示词在后（KB 提示词可叠加意图规则）。

共享 graph 架构：工具在 create_fitcream_agent 编译时固化，无法按请求真正增删，
故通过 wrap_model_call 过滤本轮模型可见工具实现等价效果（模型请求视图，不落
checkpoint、不改前端契约）。

知识库耦合：knowledge_query 意图的注入需 KB 开关开启，统一走
runtime/config_flags.get_config_flag 读取（消除中间件之间的跨模块 import）。

无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
"""

import logging
from typing import Any, Optional

from langchain.messages import HumanMessage

from src.agents.harness.orchestration.prompts.system import (
    CONTEXT_PROMPTS,
    INTENT_CLASSIFY_PROMPT,
    INTENT_KEYWORDS,
    INTENT_NEGATIVE_KEYWORDS,
    INTENT_PROMPTS,
    MEAL_IMAGE_KEYWORDS,
)
from src.agents.harness.runtime.config_flags import get_config_flag
from src.agents.harness.runtime.middleware.transient_prompt import (
    TransientPromptMiddleware,
)

logger = logging.getLogger("fitcream.agent")

# 单轮最多注入的意图提示词数量（防止多个意图叠加失控）
MAX_INTENTS = 3

# 非 plan_design 会话中 plan_creation 的替代提示词键：完整计划设计（plan-execute）
# 流程只允许「为我设计健身计划」按钮进入的会话（configurable.plan_design）触发；
# 普通聊天里用户提及计划设计时，只注入「引导点击按钮」的轻量提示词。
PLAN_CREATION_BUTTON_INTENT = "plan_creation_button"

# 受知识库回答开关门控的工具名（须与 knowledge_tools.py 中 @tool 函数名一致）
KB_TOOLS = ("search_knowledge_base", "read_kb_document", "list_my_knowledge_bases")


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


def kb_enabled_from_config() -> bool:
    """从当前 run 的 RunnableConfig.configurable 解析 kb_enabled 标志。

    统一走 get_config_flag（runtime/config_flags.py），缺失/falsy/异常一律视为关闭。
    保留此薄封装供外部调用方向后兼容。
    """
    return get_config_flag("kb_enabled")


def _tool_name(tool: Any) -> str:
    """兼容 BaseTool 与 provider 工具 dict 两种形态取工具名。"""
    if isinstance(tool, dict):
        return str(tool.get("name") or "")
    return getattr(tool, "name", "") or ""


class RequestGateMiddleware(TransientPromptMiddleware):
    """
    用户请求门控中间件 - 意图识别注入 + 知识库回答开关。

    wrap_model_call（基类 TransientPromptMiddleware 统一实现）：
    1. ``_filter_tools``：kb_enabled 关闭时从 request.tools 移除 KB 工具
    2. ``_prompt``：检测用户意图，把命中的全部意图专项提示词 + KB 优先提示词
       临时合并进 request.system_message（F1：不落 checkpoint）

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

    # ===== 意图识别（迁移自 IntentMiddleware） =====

    def _classify_with_llm(self, text: str) -> Optional[str]:
        """用轻量分类模型兜底判断意图（仅关键词无命中且开关开启时调用）。"""
        classifier = self.llm_classifier
        if classifier is None:
            logger.info(
                "[RequestGate] intent_classify_llm 已开启但未配置 llm_classifier，跳过兜底"
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
            logger.info("[RequestGate] LLM 兜底分类结果不可识别: %r", label)
        except Exception as e:
            logger.warning("[RequestGate] LLM 兜底分类失败: %s", e)
        return None

    def _compute_intent_prompt(self, messages: list) -> Optional[str]:
        """计算本轮需要注入的意图提示词（无命中/门控拦截时返回 None）。

        语义与迁移前 IntentMiddleware 一致：仅最新消息为
        HumanMessage 时检测并注入，tool 循环（ToolMessage/AIMessage）不重复注入。
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
        # 开关关闭（configurable.kb_enabled falsy）时跳过注入，避免模型想调不可见的
        # KB 工具。
        if "knowledge_query" in intents and not get_config_flag("kb_enabled", False):
            intents = [i for i in intents if i != "knowledge_query"]
            if not intents:
                logger.info("[RequestGate] Detected: knowledge_query (skipped: KB disabled)")
                return None

        # 拼接所有命中意图的专项提示词（按优先级顺序）
        prompts = [INTENT_PROMPTS[i] for i in intents if INTENT_PROMPTS.get(i)]
        if not prompts:
            return None

        logger.info(f"[RequestGate] Detected: {intents}")

        # 多意图提示词合并为一个字符串，经 system_message 临时注入（不落 checkpoint）
        return "\n\n".join(prompts)

    # ===== 知识库回答开关（迁移自 KBGateMiddleware） =====

    def _filter_tools(self, request):
        """kb_enabled 关闭时从本轮模型可见工具中移除 KB 工具（无变化则原样返回）。"""
        if kb_enabled_from_config():
            return request
        filtered = [t for t in request.tools if _tool_name(t) not in KB_TOOLS]
        if len(filtered) == len(request.tools):
            return request
        return request.override(tools=filtered)

    def _kb_prompt(self, messages: list) -> Optional[str]:
        """kb_enabled 开启且最新消息为 HumanMessage 时返回 KB 优先提示词。"""
        if not kb_enabled_from_config():
            return None

        # 提示词缺失（context_prompt/kb_answer.md 被删）时跳过注入，保持安全
        kb_answer_prompt = CONTEXT_PROMPTS.get("kb_answer")
        if not kb_answer_prompt:
            logger.warning("[RequestGate] context_prompt/kb_answer.md 缺失，跳过注入")
            return None

        if not messages:
            return None

        # 仅在用户发送新消息时注入（跳过 ToolMessage / AIMessage）
        if not isinstance(messages[-1], HumanMessage):
            return None

        logger.info("[RequestGate] 知识库回答已开启，注入 KB 优先提示词")
        return kb_answer_prompt

    # ===== 组合门控（意图提示词 + KB 提示词 + 工具过滤） =====

    def _prompt(self, messages: list) -> Optional[str]:
        """基类 hook 实现：合并意图提示词与 KB 优先提示词（意图在前，KB 在后）。"""
        parts = [
            p
            for p in (self._compute_intent_prompt(messages), self._kb_prompt(messages))
            if p
        ]
        if not parts:
            return None
        return "\n\n".join(parts)
