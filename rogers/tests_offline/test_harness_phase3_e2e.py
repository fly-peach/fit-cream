"""
阶段三端到端：TerminalToolMiddleware 终止语义集成验证（用 Fake 模型，不连 DB）。

验证（对齐 plan 3.1 校验）：
- 白名单工具：run 在工具后直接结束，无额外 LLM 轮（无最终文本 AIMessage）
- 非白名单工具：仍多一轮 LLM（模型在工具结果后产出最终文本）
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain.agents import create_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from src.agents.harness.runtime.middleware.terminal_tool import TerminalToolMiddleware


@tool
def terminal_tool(value: str) -> str:
    """终结测试工具（结果自明）。"""
    return f"已设置：{value}"


@tool
def normal_tool(value: str) -> str:
    """普通测试工具。"""
    return f"普通结果：{value}"


class _CountingChatModel(BaseChatModel):
    """按序返回「工具调用 -> 最终总结」的假模型，并记录调用次数。"""

    tool_name: str = "terminal_tool"
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "counting-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.calls += 1
        if self.calls == 1:
            msg = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tool_name,
                        "args": {"value": "x"},
                        "id": "call_1",
                        "type": "tool_call",
                    }
                ],
            )
        else:
            msg = AIMessage(content="这是最终总结")
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _make_agent(whitelist):
    model = _CountingChatModel(tool_name="terminal_tool" if whitelist else "normal_tool")
    middleware = []
    if whitelist:
        middleware.append(TerminalToolMiddleware(terminal_tools=whitelist))
    agent = create_agent(
        model=model,
        tools=[terminal_tool, normal_tool],
        system_prompt="你是测试助手",
        middleware=middleware,
    )
    return agent, model


def test_terminal_tool_ends_without_extra_llm():
    agent, model = _make_agent({"terminal_tool"})
    result = agent.invoke({"messages": [HumanMessage(content="帮我设置")]})
    # 模型只被调用一次（产出工具调用），工具后直接结束，无额外 LLM 总结
    assert model.calls == 1
    assert not any(
        isinstance(m, AIMessage) and "最终总结" in m.content for m in result["messages"]
    )
    # 工具结果在消息历史中可见（前端据此内联渲染）
    assert any(isinstance(m, ToolMessage) and m.status != "error" for m in result["messages"])


def test_normal_tool_still_gets_extra_llm():
    agent, model = _make_agent(None)
    result = agent.invoke({"messages": [HumanMessage(content="帮我执行")]})
    # 非白名单工具：工具执行后再多一轮 LLM 产出最终总结
    assert model.calls == 2
    assert any(isinstance(m, AIMessage) and "最终总结" in m.content for m in result["messages"])
