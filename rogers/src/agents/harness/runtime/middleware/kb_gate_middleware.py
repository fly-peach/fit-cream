"""
知识库回答开关中间件（按请求门控 KB 工具 + 注入 KB 优先提示词）

前端输入栏「知识库回答」开关（默认关闭，localStorage 全局偏好）：
- 开启：本轮请求模型可见 3 个 KB 工具，且在用户新消息时临时合并
  CONTEXT_PROMPTS["kb_answer"] 到 request.system_message（优先检索用户订阅的
  知识库作答，带站内出处链接）
- 关闭：wrap_model_call 从 request.tools 移除 3 个 KB 工具（模型完全看不到），
  等价于未注入

共享 graph 架构：工具在 create_fitcream_agent 编译时固化，无法按请求真正增删，
故通过 wrap_model_call 过滤本轮模型可见工具实现等价效果。

F1：KB 优先提示词迁移到 wrap_model_call 经 system_message 临时注入（不落
checkpoint），不再经 before_model 持久化到消息历史。

运行时标志解析：chat.py 把请求体 kb_enabled 写入 RunnableConfig.configurable，
本中间件经 langgraph.config.get_config() 读取（仿 memory_update._resolve_ids 模式），
中间件自身无实例级可变状态，并发 run 互不影响。

提示词来源：KB 回答提示词存放于 orchestration/prompts/context_prompt/kb_answer.md
（与 injection_prompt/ 平级），由 system.py CONTEXT_PROMPTS 在启动时扫描加载。
不能放进 injection_prompt/ 目录（system.py _load_intent_prompts 会自动扫描该目录
每个 .md 为意图键，造成误注入）。
"""

import logging
from typing import Any, Optional

from langchain.agents.middleware import AgentMiddleware

from src.agents.harness.runtime.config_flags import get_config_flag
from src.agents.harness.orchestration.prompts.system import CONTEXT_PROMPTS
from src.agents.harness.runtime.middleware.prompt_injection import merge_system_prompt
from src.agents.harness.runtime.middleware.robust import model_hook_fail_open
from langchain.messages import HumanMessage

logger = logging.getLogger("fitcream.agent")

# 受门控的知识库工具名（须与 knowledge_tools.py 中 @tool 函数名一致）
KB_TOOLS = ("search_knowledge_base", "read_kb_document", "list_my_knowledge_bases")


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


class KBGateMiddleware(AgentMiddleware):
    """知识库回答开关中间件 - 按请求过滤 KB 工具 + 注入 KB 优先提示词。

    - wrap_model_call：kb_enabled 为 falsy 时从 request.tools 移除 3 个 KB 工具
      （仅影响本轮模型可见工具，checkpoint 中已存消息不受影响）；
      kb_enabled 为 truthy 且最新消息为 HumanMessage 时，把 KB 优先提示词临时
      合并进 request.system_message（F1：不落 checkpoint，同 IntentMiddleware 模式）

    无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
    """

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
            logger.warning("[KBGate] context_prompt/kb_answer.md 缺失，跳过注入")
            return None

        if not messages:
            return None

        # 仅在用户发送新消息时注入（跳过 ToolMessage / AIMessage）
        if not isinstance(messages[-1], HumanMessage):
            return None

        logger.info("[KBGate] 知识库回答已开启，注入 KB 优先提示词")
        return kb_answer_prompt

    @model_hook_fail_open
    def wrap_model_call(self, request, handler):
        request = self._filter_tools(request)
        prompt = self._kb_prompt(request.messages)
        if prompt:
            request = merge_system_prompt(request, prompt)
        return handler(request)

    @model_hook_fail_open
    async def awrap_model_call(self, request, handler):
        request = self._filter_tools(request)
        prompt = self._kb_prompt(request.messages)
        if prompt:
            request = merge_system_prompt(request, prompt)
        return await handler(request)
