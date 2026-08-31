"""
goal-knowledge 知识层路由测试（v2：身材原型扁平行 + 动作组卡片）

覆盖：
- GET /api/goal-knowledge：按性别取行、toned_curves 不出现在 male
- GET /api/goal-knowledge/groups：卡片结构（image/兜底指标/动作组含 ID、末组拉伸）
"""
import pytest

from src.fitme.services.goal_knowledge_seed import seed_goal_knowledge
from tests.util import create_exercise


@pytest.fixture
async def goal_seed(db_session):
    await seed_goal_knowledge(db_session)
    await db_session.commit()
    return True


def _unwrap(resp) -> dict:
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]


async def test_get_goal_knowledge_flat_rows(user_client, goal_seed):
    data = _unwrap(await user_client.get("/api/goal-knowledge"))
    assert data["gender"] in ("male", "female")
    rows = data["archetypes"]
    assert rows, "种子后应有原型行"
    assert all({"key", "gender", "target_metrics", "target_exercises"} <= set(r) for r in rows)
    keys = {(r["key"], r["gender"]) for r in rows}
    if data["gender"] == "male":
        assert ("toned_curves", "male") not in keys
    else:
        assert ("toned_curves", "female") in keys


async def test_goal_knowledge_groups(user_client, db_session, goal_seed):
    await create_exercise(db_session, name="杠铃卧推")
    await create_exercise(db_session, name="腘绳肌拉伸")

    data = _unwrap(await user_client.get("/api/goal-knowledge/groups"))
    assert data["gender"] in ("male", "female")
    groups = data["groups"]
    assert groups, "应有动作组卡片"
    card = groups[0]
    assert card["image"] == f"/static/goals/{card['key']}_{card['gender']}.webp"
    assert card["target_exercise_goal"], "兜底达成指标不应为空"
    assert card["exercise_groups"][-1]["group"] == "拉伸", "末组必须为拉伸"
    resolved = [e for grp in card["exercise_groups"] for e in grp["exercises"]]
    assert all("id" in e and "name" in e for e in resolved)
