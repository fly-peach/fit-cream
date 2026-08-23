"""
阶段一端到端：SameToolLimitMiddleware 改用 wrap_tool_call 后真正拦截执行。

验证（对齐 plan 1.3 校验）：
- 同一工具连调超过 max_same_tool_calls 后，后续调用**不再执行**（副作用计数不增加），
  而是返回 error ToolMessage。
- 用 Fake 模型强制连续调用同一工具，断言工具实际执行次数 == max。
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from src.agents.harness.runtime.middleware.rate_limit import SameToolLimitMiddleware


class _Calls:
    def __init__(self):
        self.n = 0


_CALLS = _Calls()


@tool
def counting_tool(value: str) -> str:
    """记录真实执行次数的测试工具。"""
    _CALLS.n += 1
    return f"executed-{_CALLS.n}"


class _LoopModel(BaseChatModel):
    """前 N 次都返回同一工具的调用，之后返回最终文本。"""

    max_loop: int = 6

    @property
    def _llm_type(self) -> str:
        return "loop-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # 统计历史中 counting_tool 已出现的 ToolMessage 数，超出循环上限则收尾
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
        if len(tool_msgs) >= self.max_loop:
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content="结束"))])
        return ChatResult(
            generations=[
                ChatGeneration(
                    message=AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "counting_tool",
                                "args": {"value": "x"},
                                "id": f"call_{len(tool_msgs)}",
                                "type": "tool_call",
                            }
                        ],
                    )
                )
            ]
        )


def test_same_tool_blocked_after_max():
    _CALLS.n = 0
    model = _LoopModel(max_loop=6)
    agent = create_agent(
        model=model,
        tools=[counting_tool],
        system_prompt="测试",
        middleware=[SameToolLimitMiddleware(max_same_tool_calls=5)],
    )
    result = agent.invoke({"messages": [HumanMessage(content="连调同一工具")]})

    # 工具真实执行次数被封顶为 5 次（第 6 次被 wrap_tool_call 短路拦截）
    assert _CALLS.n == 5

    # 被拦截的调用产生 error ToolMessage（模型可感知，但工具未执行）
    error_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage) and m.status == "error"]
    assert len(error_msgs) >= 1
    assert "has been called" in error_msgs[0].content
