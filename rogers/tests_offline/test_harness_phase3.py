"""
阶段三：terminate 语义不变量单测（不依赖真实 LLM、不 import 生产 DB）。

覆盖 TerminalToolMiddleware：
- 白名单工具批全部成功 -> jump_to=end（跳过后续自动 LLM）
- 非白名单 / 混合批 / 失败 / 悬挂 / 未处于工具批后 -> 不终结
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.agents.harness.runtime.middleware.terminal_tool import TerminalToolMiddleware

TERMINAL = {"set_nutrition_goals_tool"}


def _tool_call(tool_name: str, call_id: str) -> dict:
    return {"name": tool_name, "args": {}, "id": call_id, "type": "tool_call"}


def _ai_with_tools(tool_calls: list[dict]) -> AIMessage:
    return AIMessage(content="", tool_calls=tool_calls)


class TestTerminalToolMiddleware:
    def test_all_terminal_success_jumps_to_end(self):
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
                ToolMessage(content="已设置营养目标", tool_call_id="c1"),
            ]
        }
        assert mw.before_model(state, None) == {"jump_to": "end"}

    async def test_abefore_model_jumps_to_end(self):
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
                ToolMessage(content="ok", tool_call_id="c1"),
            ]
        }
        assert await mw.abefore_model(state, None) == {"jump_to": "end"}

    def test_non_terminal_tool_not_jump(self):
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("checkin_tool", "c1")]),
                ToolMessage(content="打卡成功", tool_call_id="c1"),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_mixed_batch_not_jump(self):
        # 批内混入非白名单工具 -> 不终结（批内全部终结才终止）
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools(
                    [
                        _tool_call("set_nutrition_goals_tool", "c1"),
                        _tool_call("checkin_tool", "c2"),
                    ]
                ),
                ToolMessage(content="ok", tool_call_id="c1"),
                ToolMessage(content="ok", tool_call_id="c2"),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_failed_terminal_tool_not_jump(self):
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
                ToolMessage(content="Error", tool_call_id="c1", status="error"),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_pending_tool_call_not_jump(self):
        # 工具调用了但尚无对应结果（悬挂）-> 不终结
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_not_after_tools_round(self):
        # 最新消息是用户消息（新一轮对话）-> 不终结
        mw = TerminalToolMiddleware(terminal_tools=TERMINAL)
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
                ToolMessage(content="ok", tool_call_id="c1"),
                HumanMessage(content="谢谢"),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_empty_whitelist_disabled(self):
        mw = TerminalToolMiddleware(terminal_tools=set())
        state = {
            "messages": [
                _ai_with_tools([_tool_call("set_nutrition_goals_tool", "c1")]),
                ToolMessage(content="ok", tool_call_id="c1"),
            ]
        }
        assert mw.before_model(state, None) is None

    def test_multi_terminal_batch_success(self):
        mw = TerminalToolMiddleware(terminal_tools={"tool_a", "tool_b"})
        state = {
            "messages": [
                _ai_with_tools(
                    [_tool_call("tool_a", "c1"), _tool_call("tool_b", "c2")]
                ),
                ToolMessage(content="ok", tool_call_id="c1"),
                ToolMessage(content="ok", tool_call_id="c2"),
            ]
        }
        assert mw.before_model(state, None) == {"jump_to": "end"}
