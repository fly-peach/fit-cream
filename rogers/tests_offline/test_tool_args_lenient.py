# -*- coding: utf-8 -*-
"""工具参数容错 + resume 悬空修复安全回归测试（2026-08-29 三事故）

覆盖：
- Bug1/Bug3 根因：/chat/resume 绝不可再调用 _repair_dangling_tool_calls
  （待审批 pending tool_calls 会被误判悬空 -> 追加「未执行」合成 ToolMessage
  -> 真实落库被跳过 -> 模型见「异常中断」死循环重试）
- Bug2 根因：qwen 把嵌套数组字符串化（changes='[...]' / todos / exercises / days），
  严格 pydantic 校验炸 -> 重试触发限流。coerce_json_list 统一容错。
"""
import inspect
import json

from src.agents.harness.tools._common import coerce_json_list, stringify_scalars


class TestCoerceJsonList:
    def test_json_string_parsed(self):
        v = json.dumps([{"a": "1"}, {"a": "2"}], ensure_ascii=False)
        assert coerce_json_list(v) == [{"a": "1"}, {"a": "2"}]

    def test_single_dict_wrapped(self):
        assert coerce_json_list({"a": 1}) == [{"a": 1}]

    def test_list_with_string_items_parsed(self):
        v = ['{"a": 1}', {"b": 2}, "not-json", 3]
        assert coerce_json_list(v) == [{"a": 1}, {"b": 2}]

    def test_garbage_string_degrades_to_none(self):
        assert coerce_json_list('这是模型写的说明文字"没有 JSON"') is None

    def test_none_passthrough(self):
        assert coerce_json_list(None) is None

    def test_plain_list_passthrough(self):
        v = [{"a": 1}, "b"]
        assert coerce_json_list(v) == [{"a": 1}]

    def test_stringify_scalars_value_variants(self):
        out = stringify_scalars({"target": "体重", "detail": 72.5, "extra": [1, 2]})
        assert out == {"target": "体重", "detail": "72.5", "extra": "[1, 2]"}


class TestPresentPlanChangesLenient:
    """Bug2 事故现场：present_plan_tool.changes 字符串化"""

    def _valid(self, **kwargs):
        from src.agents.harness.tools.plan.present_plan_tool import PresentPlanInput

        return PresentPlanInput.model_validate(
            {"title": "减脂计划", "description": "8 周", "content": "|x|", **kwargs}
        )

    def test_list_of_dict_ok(self):
        item = self._valid(changes=[{"domain": "训练计划", "action": "新增", "target": "T", "detail": "D"}])
        assert item.changes[0]["domain"] == "训练计划"

    def test_stringified_json_changes_parsed(self):
        changes = json.dumps(
            [
                {"domain": "训练计划", "action": "新增", "target": "减脂计划", "detail": "每周5练"},
                {"domain": "用户档案", "action": "更新", "target": "体重", "detail": 72},
            ],
            ensure_ascii=False,
        )
        item = self._valid(changes=changes)
        assert len(item.changes) == 2
        assert item.changes[1]["detail"] == "72"  # 数字值归一为字符串

    def test_prose_garbage_changes_degrades(self):
        item = self._valid(changes="这是变更清单：1. 新增计划 2. 更新档案")
        assert item.changes is None


class TestPlanQueueTodosLenient:
    def test_stringified_todos_parsed(self):
        from src.agents.harness.tools.plan.plan_queue_tools import PlanQueue

        todos = json.dumps(
            [
                {"id": "intake-body", "title": "收集基础身体数据", "status": "completed"},
                {"id": "assemble", "title": "装配完整提案", "status": "in_progress"},
            ],
            ensure_ascii=False,
        )
        q = PlanQueue(title="设计", todos=todos)
        assert [t.id for t in q.todos] == ["intake-body", "assemble"]

    def test_explicit_args_schema_todos_lenient(self):
        from src.agents.harness.tools.plan.plan_queue_tools import PresentPlanQueueInput

        todos = '{"id":"x","title":"t"}'  # 单元素字符串化
        q = PresentPlanQueueInput(title="设计", todos=[todos, [{"bad": None}]])
        assert [t.id for t in q.todos] == ["x"]

    def test_day_design_exercises_lenient(self):
        from src.agents.harness.tools.plan.plan_queue_tools import DayDesign

        ex = json.dumps(
            [{"name": "杠铃卧推", "exercise_type": "strength", "sets": 4, "reps": 8}],
            ensure_ascii=False,
        )
        d = DayDesign(day_of_week=1, focus="胸", day_type="strength", exercises=ex)
        assert d.exercises[0].name == "杠铃卧推"

    def test_outline_days_lenient(self):
        from src.agents.harness.tools.plan.plan_queue_tools import PresentOutlineInput

        days = json.dumps(
            [
                {"day_of_week": 1, "focus": "胸+三头", "day_type": "strength"},
                {"day_of_week": 2, "focus": "休息", "day_type": "rest"},
            ],
            ensure_ascii=False,
        )
        o = PresentOutlineInput(title="大纲", strategy="上下肢分化", days=days)
        assert len(o.days) == 2


class TestResumeNoDanglingRepair:
    """Bug1/Bug3 回归护栏：resume 路径不可再破坏 pending 中断"""

    def test_resume_handler_does_not_repair(self):
        import app.routers.chat as chat_mod

        src = inspect.getsource(chat_mod.resume_conversation)
        assert "_repair_dangling_tool_calls" not in src, (
            "resume 前禁止悬空修复：会把待审批的 pending tool_calls 误判为残留并破坏落库"
        )

    def test_message_handler_still_repairs(self):
        import app.routers.chat as chat_mod

        src = inspect.getsource(chat_mod.send_message)
        assert "_repair_dangling_tool_calls" in src, "/message 的放弃-续聊修复路径必须保留"

    def test_synth_message_not_misleading(self):
        import app.routers.chat as chat_mod

        src = inspect.getsource(chat_mod._repair_dangling_tool_calls)
        assert "因异常中断" not in src, "合成 ToolMessage 不应使用「异常中断」措辞（模型误报系统崩溃）"
