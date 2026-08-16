"""
意图识别中间件（渐进式提示词注入）

基于 LangChain AgentMiddleware 的 before_model hook：
1. 检测最新用户消息的意图（关键词匹配 + 图片检测）
2. 注入对应的意图专项提示词（SystemMessage）
3. 实现"渐进式披露"——仅注入与当前意图相关的规则

架构：
    用户消息 -> IntentMiddleware.before_model
                    |
                    v
              detect_intent(message)
                    |
            ┌───────┴────────┐
            |  图片检测       |  关键词匹配
            v                v
      meal_image_analysis /  plan_creation / checkin / ...
      image_analysis
                    |
                    v
          注入 INTENT_PROMPTS[intent]
          (SystemMessage -> messages)

效果：
- 基础提示词始终存在（身份、能力概览、核心规则）
- 意图专项规则按需注入（减少 token，模型更聚焦）
- 每次用户新消息时重新检测意图
"""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from src.agents.harness.orchestration.prompts.system import (
    INTENT_KEYWORDS,
    INTENT_PROMPTS,
    MEAL_IMAGE_KEYWORDS,
)

logger = logging.getLogger("fitcream.agent")


def detect_intent(message: HumanMessage) -> str:
    """
    从用户消息中检测意图。

    检测策略（按优先级）：
    1. 图片检测：content 含 image_url 块 -> 伴随文本命中饮食关键词则 meal_image_analysis，
       否则 image_analysis
    2. 关键词匹配：按 INTENT_KEYWORDS 表匹配最高优先级意图
    3. 默认：general_chat

    Args:
        message: 用户消息（HumanMessage）

    Returns:
        意图字符串（如 "plan_creation", "image_analysis", "meal_image_analysis", "general_chat"）

    Example:
        >>> msg = HumanMessage(content="帮我制定减脂计划")
        >>> detect_intent(msg)
        'plan_creation'

        >>> msg = HumanMessage(content=[
        ...     {"type": "text", "text": "分析一下我的深蹲动作"},
        ...     {"type": "image_url", "image_url": {"url": "data:..."}},
        ... ])
        >>> detect_intent(msg)
        'image_analysis'

        >>> msg = HumanMessage(content=[
        ...     {"type": "text", "text": "帮我看看这餐吃了多少热量"},
        ...     {"type": "image_url", "image_url": {"url": "data:..."}},
        ... ])
        >>> detect_intent(msg)
        'meal_image_analysis'
    """
    content = message.content

    # 1. 图片检测（多模态消息，content 为 list）
    if isinstance(content, list):
        has_image = any(
            isinstance(block, dict) and block.get("type") == "image_url"
            for block in content
        )
        if has_image:
            text = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
            # 伴随文本含饮食关键词 -> 饮食热量识别专项流程
            if any(kw in text for kw in MEAL_IMAGE_KEYWORDS):
                return "meal_image_analysis"
            return "image_analysis"

    # 2. 提取文本内容
    if isinstance(content, list):
        text = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        text = str(content) if content else ""

    # 3. 关键词匹配（按 INTENT_KEYWORDS 顺序，先匹配优先返回）
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return intent

    # 4. 默认
    return "general_chat"


class IntentMiddleware(AgentMiddleware):
    """
    意图识别中间件 - 渐进式提示词注入。

    在 before_model 阶段：
    1. 检查最新消息是否为用户消息（HumanMessage）
    2. 检测用户意图（关键词匹配 + 图片检测）
    3. 注入意图专项提示词（SystemMessage）

    渐进式披露：只有与当前意图相关的规则被注入，减少 token 消耗，
    让模型更聚焦于当前任务。

    注入时机：仅在最新消息为 HumanMessage 时注入（即用户刚发送新消息时）。
    后续 model 调用（tool 执行后）不会重复注入，因为最新消息为 ToolMessage。

    无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
    """

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """
        在模型调用前注入意图专项提示词。

        检测最新用户消息的意图，注入对应的 INTENT_PROMPTS[section]。
        仅当最新消息为 HumanMessage 时触发（避免 tool 循环中重复注入）。
        """
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]

        # 仅在用户发送新消息时注入（跳过 ToolMessage / AIMessage）
        if not isinstance(last_msg, HumanMessage):
            return None

        # 检测意图
        intent = detect_intent(last_msg)

        # 获取意图专项提示词
        intent_prompt = INTENT_PROMPTS.get(intent)
        if not intent_prompt:
            return None

        # knowledge_query 意图注入「优先知识库检索」引导，与 KB 工具门控矛盾：
        # 开关关闭（configurable.kb_enabled falsy）时跳过注入，避免模型想调不可见的 KB 工具
        if intent == "knowledge_query":
            from src.agents.harness.runtime.middleware.kb_gate_middleware import (
                kb_enabled_from_config,
            )

            if not kb_enabled_from_config():
                logger.info("[Intent] Detected: knowledge_query (skipped: KB disabled)")
                return None

        logger.info(f"[Intent] Detected: {intent}")

        # 注入意图专项 SystemMessage
        return {"messages": [SystemMessage(content=intent_prompt)]}
