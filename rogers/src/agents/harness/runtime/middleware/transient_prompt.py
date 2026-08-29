"""
临时提示词注入中间件基类（合并语义 + 自动 sync/async 桥接 + fail-open）

收敛「按用户最新消息注入提示词」这一族中间件（RequestGateMiddleware /
PlanQueueMiddleware / ContentValidationMiddleware）的 wrap 样板：三者本质都是
wrap_model_call 里计算一段 ``Optional[str]`` 提示词 -> merge_system_prompt 合并进
request.system_message（F1：不落 checkpoint），且 sync/async 两份实现一字不差。

基类统一实现 wrap_model_call / awrap_model_call：
- ``_filter_tools(request)``：可选，注入前对请求做视图变换（如 RequestGate 的
  KB 工具过滤），先于提示词注入
- ``_prompt(messages) -> Optional[str]``：子类唯一要写的纯函数（None = 不注入）
- 异常经 @model_hook_fail_open 围栏 fail-open（ERROR 日志 + 放行 handler），
  语义 = 少注入一段提示词，不炸请求（robust.py，2026-08-28 事故铁律）

无实例级可变状态：编译进共享 graph，并发运行互不影响。
"""

import logging
from typing import Optional

from langchain.agents.middleware import AgentMiddleware

from src.agents.harness.runtime.middleware.prompt_injection import merge_system_prompt
from src.agents.harness.runtime.middleware.robust import model_hook_fail_open

logger = logging.getLogger("fitcream.agent")


class TransientPromptMiddleware(AgentMiddleware):
    """
    临时提示词注入中间件基类。

    子类契约：
    - ``_prompt(messages) -> Optional[str]``：本轮需要注入的提示词文本；
      None 表示不注入（原样放行）。仅最新消息为 HumanMessage 时注入的门控
      语义由子类在此实现。
    - ``_filter_tools(request)``：可选，注入前对 request 做视图变换
      （如按开关过滤工具）；默认原样返回。
    """

    def _prompt(self, messages: list) -> Optional[str]:
        """子类实现：计算本轮注入的提示词（None = 不注入）。"""
        return None

    def _filter_tools(self, request):
        """子类可选实现：注入前对 request 做视图变换（如过滤工具）。默认原样返回。"""
        return request

    @model_hook_fail_open
    def wrap_model_call(self, request, handler):
        """同步路径：视图变换（可选）-> 提示词合并 -> 放行模型调用。"""
        request = self._filter_tools(request)
        prompt = self._prompt(request.messages)
        if prompt:
            request = merge_system_prompt(request, prompt)
        return handler(request)

    @model_hook_fail_open
    async def awrap_model_call(self, request, handler):
        """异步路径（生产 SSE 走这里）：同 wrap_model_call。"""
        request = self._filter_tools(request)
        prompt = self._prompt(request.messages)
        if prompt:
            request = merge_system_prompt(request, prompt)
        return await handler(request)
