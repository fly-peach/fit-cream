"""
Part II：动作库检索质量相关纯逻辑单测（不依赖 LLM、不连 DB）。

覆盖（schema v2）：
- A1 build_embedding_text 检索文本标签化（名称中英/类型/主要锻炼/协同肌群/部位/器械/难度/简介）
- A2 get_exercises_tool 返回白名单精简（描述首句摘要）
- B1 黄金集 JSON 加载 + v2 schema 结构校验 + relevant_names 均可命中 dataset
- B2 评估器纯计算（_recall / _mrr / _precision / _hit_rate）
- C1 RRF 融合纯函数（ExerciseService.rrf_fuse）
- C2 rerank_texts 回退（未启用/异常回退原序）
- C3 infer_difficulty 规则表（exercise_seed）

说明：构建 Exercise 模型实例不产生 DB 访问；dataset 读取为本地 JSON。
"""

import os

# 先于任何 app.config 读取设置环境，保证 rerank_texts 回退测试确定（offline）
os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")
os.environ["RERANK_ENABLED"] = "false"

from src.fitme.models.exercise import Exercise  # noqa: E402
from src.fitme.services.exercise_service import ExerciseService  # noqa: E402
from src.fitme.services.search_recall_service import SearchRecallService  # noqa: E402
from src.fitme.services.exercise_seed import infer_difficulty  # noqa: E402
from src.agents.harness.runtime.memory.embeddings import rerank_texts  # noqa: E402
from src.agents.harness.tools.training.exercise_tools import _first_sentence  # noqa: E402


class TestBuildEmbeddingText:
    def test_includes_all_new_fields(self):
        ex = Exercise(
            name="杠铃卧推",
            name_en="Barbell Bench Press",
            muscle_group="chest",
            muscle_subgroup_zh="胸大肌中部",
            target_zh="胸大肌",
            equipment_zh="杠铃",
            equipment="barbell",
            body_part_zh="胸部",
            category="compound",
            is_compound=True,
            difficulty="intermediate",
            description="经典胸部训练。",
            secondary_muscles_zh=["肱三头肌", "前束"],
        )
        text = ExerciseService.build_embedding_text(ex)
        assert "动作：杠铃卧推（Barbell Bench Press）" in text
        assert "类型：复合动作（compound）" in text
        assert "主要锻炼：胸大肌" in text
        assert "身体部位：胸部" in text
        assert "器械：杠铃（barbell）" in text
        assert "难度：中级（intermediate）" in text
        assert "协同肌群：肱三头肌、前束" in text
        assert "简介：经典胸部训练。" in text

    def test_empty_secondary_omitted(self):
        ex = Exercise(name="平板支撑", category="isolation", is_compound=False)
        text = ExerciseService.build_embedding_text(ex)
        assert "类型：孤立动作（isolation）" in text
        assert "协同肌群" not in text
        assert "简介" not in text


class TestFirstSentence:
    def test_stops_at_chinese_period(self):
        assert _first_sentence("经典的胸部训练动作。这是第二句。") == "经典的胸部训练动作。"

    def test_truncates_long_first_sentence(self):
        long = "很" * 200 + "。后文"
        out = _first_sentence(long, max_len=80)
        assert len(out) == 81
        assert out.endswith("…")

    def test_empty_returns_empty(self):
        assert _first_sentence("") == ""
        assert _first_sentence(None) == ""


class TestGoldenSetV2:
    def test_golden_set_loads(self):
        golden = SearchRecallService.load_golden_set()
        assert len(golden) >= 20

    def test_every_entry_has_exactly_one_relevance_kind(self):
        golden = SearchRecallService.load_golden_set()
        for q in golden:
            assert (q.get("relevant_filter") is not None) != (
                q.get("relevant_names") is not None
            ), f"必须二选一（relevant_filter XOR relevant_names）: {q.get('query')}"

    def test_filter_entries_have_valid_structure(self):
        golden = SearchRecallService.load_golden_set()
        for q in golden:
            f = q.get("relevant_filter")
            if f is None:
                continue
            assert isinstance(f, dict), q.get("query")
            for key in ("muscle_group", "equipment", "difficulty", "category"):
                if key in f:
                    assert f[key], f"{q.get('query')} 的 {key} 为空"
            if "name_any" in f:
                assert isinstance(f["name_any"], list) and f["name_any"], (
                    q.get("query") + " 的 name_any 须为非空列表"
                )
                assert all(isinstance(t, str) for t in f["name_any"])

    def test_keyword_terms_valid(self):
        golden = SearchRecallService.load_golden_set()
        for q in golden:
            terms = q.get("keyword_terms")
            if terms is not None:
                assert isinstance(terms, list) and terms
                assert all(isinstance(t, str) for t in terms)

    def test_every_relevant_name_resolves_in_dataset(self):
        from src.fitme.services.exercise_seed import load_dataset

        records = load_dataset()
        known = set()
        for rec in records:
            known.add((rec["name"] or "").strip().lower())
            if rec["name_en"]:
                known.add(rec["name_en"].strip().lower())

        golden = SearchRecallService.load_golden_set()
        missing = []
        for q in golden:
            for name in q.get("relevant_names") or []:
                if name.strip().lower() not in known:
                    missing.append(name)
        assert not missing, f"黄金集引用不存在于 dataset 的动作名: {missing}"

    def test_zero_hit_negative_has_empty_relevant(self):
        golden = SearchRecallService.load_golden_set()
        zero = [q for q in golden if q.get("relevant_names") == []]
        assert zero, "应包含零命中反例（relevant_names 为空）"


class TestMetrics:
    def test_recall_ratio(self):
        assert SearchRecallService._recall(["a", "b"], {"a", "c"}) == 0.5

    def test_no_relevant_expects_zero_hits(self):
        assert SearchRecallService._recall([], set()) == 1.0
        assert SearchRecallService._recall(["a"], set()) == 0.0

    def test_mrr(self):
        assert SearchRecallService._mrr(["x", "a", "b"], {"a"}) == 0.5
        assert SearchRecallService._mrr(["a"], {"a"}) == 1.0
        assert SearchRecallService._mrr(["x", "y"], {"a"}) == 0.0
        assert SearchRecallService._mrr([], {"a"}) == 0.0

    def test_precision(self):
        assert SearchRecallService._precision(["a", "b", "c"], {"a", "b"}) == 2 / 3
        assert SearchRecallService._precision(["a"], {"a"}) == 1.0
        assert SearchRecallService._precision([], {"a"}) == 0.0

    def test_hit_rate(self):
        assert SearchRecallService._hit_rate(["x", "a"], {"a"}) == 1.0
        assert SearchRecallService._hit_rate(["a", "b"], {"c"}, top=2) == 0.0
        assert SearchRecallService._hit_rate([], {"a"}) == 0.0


class TestRRFFuse:
    def test_fuses_and_dedupes(self):
        fused = ExerciseService.rrf_fuse([["x", "y", "z"], ["y", "z", "w"]], k=60)
        assert fused[0] == "y"
        assert fused[1] == "z"
        assert set(fused) == {"x", "y", "z", "w"}

    def test_single_list_preserves_order(self):
        assert ExerciseService.rrf_fuse([["a", "b", "c"]], k=60) == ["a", "b", "c"]

    def test_empty_lists(self):
        assert ExerciseService.rrf_fuse([[], []], k=60) == []


class TestRerankTexts:
    async def test_empty_input(self):
        assert await rerank_texts("q", []) == []

    async def test_disabled_returns_original_order(self):
        # RERANK_ENABLED=false（模块顶部 env）：_load_reranker 返回 None -> 原序
        assert await rerank_texts("q", ["a", "b", "c"]) == [0, 1, 2]


class TestInferDifficulty:
    def test_keyword_beginner(self):
        assert infer_difficulty("Assisted Pull-Up", "machine", "compound") == "beginner"
        assert infer_difficulty("Beginner Workout", "bodyweight", "isolation") == "beginner"

    def test_keyword_advanced(self):
        assert infer_difficulty("One Arm Push-Up", "bodyweight", "compound") == "advanced"
        assert infer_difficulty("Weighted Dip", "bodyweight", "compound") == "advanced"
        assert infer_difficulty("Explosive Jump Squat", "bodyweight", "compound") == "advanced"

    def test_machine_band_isolation_beginner(self):
        assert infer_difficulty("Seated Calf Raise", "machine", "isolation") == "beginner"
        assert infer_difficulty("Band Curl", "band", "isolation") == "beginner"

    def test_bodyweight_isolation_beginner(self):
        assert infer_difficulty("Plank", "bodyweight", "isolation") == "beginner"

    def test_bodyweight_isolation_stretch_not_beginner(self):
        assert infer_difficulty("Hamstring Stretch", "bodyweight", "isolation") == "intermediate"

    def test_barbell_compound_intermediate(self):
        assert infer_difficulty("Barbell Bench Press", "barbell", "compound") == "intermediate"

    def test_default_intermediate(self):
        assert infer_difficulty("Cable Row", "cable", "compound") == "intermediate"
