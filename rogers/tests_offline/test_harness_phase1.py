"""
阶段一：agent harness 健壮性 / 安全不变量单测（不依赖 LLM、不 import 生产 DB）。

覆盖：
- 1.1 skills catalog XML 转义 + 元数据校验 + diagnostics
- 1.2 提示词目录分层（context_prompt 与 injection_prompt 不互串）
- 1.3 SameToolLimit 改用 wrap_tool_call 拦截（工具不被执行）

说明：导入 src.agents.harness.* 会触发 src.agents.__init__ -> agent_graph 构建
默认 graph（无 checkpointer，不连 DB），仅需一个非空 DASHSCOPE_API_KEY 即可构造
模型客户端（不产生网络调用），故在导入前 setdefault 一个占位值保证测试可离线运行。
"""

import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")

from langchain.agents.middleware.types import ToolCallRequest  # noqa: E402
from langchain_core.messages import AIMessage  # noqa: E402

from src.agents.harness.skills.skills_loader import (  # noqa: E402
    _SKILL_NAME_RE,
    _parse_frontmatter,
    _xml_escape,
    get_catalog_prompt,
    get_skill_diagnostics,
    reload_skills,
)
from src.agents.harness.orchestration.prompts.system import (  # noqa: E402
    CONTEXT_PROMPTS,
    INTENT_PROMPTS,
)
from src.agents.harness.runtime.middleware.rate_limit import (  # noqa: E402
    SameToolLimitMiddleware,
)


# ============================================================
# 1.1 skills catalog 安全化 + 元数据校验
# ============================================================


class TestXmlEscape:
    def test_escapes_special_chars(self):
        assert _xml_escape("a & b < c > d \" e ' f") == (
            "a &amp; b &lt; c &gt; d &quot; e &apos; f"
        )

    def test_plain_text_unchanged(self):
        assert _xml_escape("plan-creation / 增肌") == "plan-creation / 增肌"

    def test_catalog_prompt_is_xml_block(self):
        prompt = get_catalog_prompt()
        assert prompt
        assert "<available_skills>" in prompt
        assert "</available_skills>" in prompt
        assert "<skill><name>" in prompt
        assert "<description>" in prompt

    def test_catalog_prompt_escapes_injection(self, monkeypatch):
        # 注入带特殊字符的 catalog，验证输出被转义
        fake_catalog = [
            {"name": "bad<skill>", "description": "desc & <script>alert(1)</script>"}
        ]
        monkeypatch.setattr(
            "src.agents.harness.skills.skills_loader.get_skill_catalog",
            lambda: fake_catalog,
        )
        prompt = get_catalog_prompt()
        assert "bad&lt;skill&gt;" in prompt
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in prompt
        assert "<script>" not in prompt


class TestFrontmatterValidation:
    def test_name_regex(self):
        assert _SKILL_NAME_RE.match("plan-creation")
        assert _SKILL_NAME_RE.match("a1-b2")
        assert not _SKILL_NAME_RE.match("Plan Creation")
        assert not _SKILL_NAME_RE.match("bad_name")
        assert not _SKILL_NAME_RE.match("bad<name>")

    def test_parse_frontmatter_basic(self):
        raw = "---\nname: plan-creation\ndescription: 描述\n---\n正文"
        name, desc, body = _parse_frontmatter(raw)
        assert name == "plan-creation"
        assert desc == "描述"
        assert body == "正文"

    def test_parse_frontmatter_no_frontmatter(self):
        name, desc, body = _parse_frontmatter("# just body")
        assert name == ""
        assert desc == ""
        assert body == "# just body"

    def test_load_skills_diagnostics(self, tmp_path, monkeypatch):
        # 构造两个问题技能：非法名 + 缺描述，验证 diagnostics 被收集
        bad_name_dir = tmp_path / "bad name dir"
        bad_name_dir.mkdir()
        (bad_name_dir / "SKILL.md").write_text(
            "---\nname: Bad Name!\ndescription: ok\n---\nbody",
            encoding="utf-8",
        )

        no_desc_dir = tmp_path / "no-desc"
        no_desc_dir.mkdir()
        (no_desc_dir / "SKILL.md").write_text("---\nname: no-desc\n---\nbody", encoding="utf-8")

        good_dir = tmp_path / "good-skill"
        good_dir.mkdir()
        (good_dir / "SKILL.md").write_text(
            "---\nname: good-skill\ndescription: good\n---\nbody",
            encoding="utf-8",
        )

        monkeypatch.setattr(
            "src.agents.harness.skills.skills_loader._SKILLS_DIR", tmp_path
        )
        reload_skills()
        diagnostics = get_skill_diagnostics()

        messages = [d["message"] for d in diagnostics]
        assert any("不符合命名规范" in m for m in messages)
        assert any("缺少 description" in m for m in messages)
        # 合法技能不产生诊断
        assert not any(d["skill"] == "good-skill" for d in diagnostics)

        # catalog 仍包含全部技能（非法名也保留，但打了 warning）
        prompt = get_catalog_prompt()
        assert "no-desc" in prompt
        assert "good-skill" in prompt


# ============================================================
# 1.2 提示词目录分层（context_prompt 与 injection_prompt 不互串）
# ============================================================


class TestPromptDirectorySeparation:
    def test_kb_answer_loaded_in_context_prompts(self):
        assert "kb_answer" in CONTEXT_PROMPTS
        assert CONTEXT_PROMPTS["kb_answer"].startswith("本轮对话已开启「知识库回答」模式")

    def test_kb_answer_not_leaked_into_intent_prompts(self):
        assert "kb_answer" not in INTENT_PROMPTS

    def test_context_prompts_no_intent_keys(self):
        for key in CONTEXT_PROMPTS:
            assert key not in INTENT_PROMPTS, f"{key} 不应同时出现在意图提示词中"

    def test_intent_prompts_loaded(self):
        assert "plan_creation" in INTENT_PROMPTS
        assert "checkin" in INTENT_PROMPTS


# ============================================================
# 1.3 SameToolLimit 改用 wrap_tool_call 拦截
# ============================================================


def _make_request(state: dict, tool_name: str = "same_tool") -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={"name": tool_name, "args": {}, "id": "call-1", "type": "tool_call"},
        tool=None,
        state=state,
        runtime=None,
    )


class TestSameToolLimitBlocking:
    def test_after_model_only_counts(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=5)
        state = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "same_tool", "args": {}, "id": "c1", "type": "tool_call"},
                        {"name": "same_tool", "args": {}, "id": "c2", "type": "tool_call"},
                    ],
                )
            ]
        }
        result = mw.after_model(state, None)
        assert result["same_tool_counts"] == {"same_tool": 2}
        assert "messages" not in result

    def test_wrap_tool_call_blocks_when_over_limit(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=5)
        state = {"same_tool_counts": {"same_tool": 6}}

        executed = []

        def handler(request):
            executed.append(True)
            return "ok"

        from langchain_core.messages import ToolMessage

        result = mw.wrap_tool_call(_make_request(state), handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert result.tool_call_id == "call-1"
        assert not executed  # 工具未被真正执行

    def test_wrap_tool_call_allows_under_limit(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=5)
        state = {"same_tool_counts": {"same_tool": 4}}

        executed = []

        def handler(request):
            executed.append(True)
            return "ok"

        result = mw.wrap_tool_call(_make_request(state), handler)
        assert result == "ok"
        assert executed == [True]

    def test_wrap_tool_call_blocked_only_after_exceed(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=1)
        # 正好 1 次：放行
        state = {"same_tool_counts": {"same_tool": 1}}
        executed = []

        def handler(request):
            executed.append(True)
            return "ok"

        mw.wrap_tool_call(_make_request(state), handler)
        assert executed == [True]

        # 第 2 次：拦截
        state2 = {"same_tool_counts": {"same_tool": 2}}
        from langchain_core.messages import ToolMessage

        result = mw.wrap_tool_call(_make_request(state2), handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"

    async def test_awrap_tool_call_blocks(self):
        mw = SameToolLimitMiddleware(max_same_tool_calls=5)
        state = {"same_tool_counts": {"same_tool": 6}}
        executed = []

        async def handler(request):
            executed.append(True)
            return "ok"

        from langchain_core.messages import ToolMessage

        result = await mw.awrap_tool_call(_make_request(state), handler)
        assert isinstance(result, ToolMessage)
        assert result.status == "error"
        assert not executed
