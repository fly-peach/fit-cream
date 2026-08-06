"""
记忆工具 (Memory Tools)

提供给 Agent 使用的记忆相关工具：
- recall_memory: 检索相关记忆（情景/语义/程序性）
- save_preference: 保存用户偏好
- save_user_fact: 保存用户事实
- list_user_profile: 列出用户画像信息
- save_event: 记录重要事件

用法：
    from src.agents.harness.tools.memory.memory_tools import create_memory_tools

    tools = create_memory_tools()
    agent = create_react_agent(llm, tools=tools)
"""

from typing import Optional
from uuid import UUID

from langchain_core.tools import tool

from app.database import async_session_factory
from src.agents.harness.runtime.memory.store import MemoryStore, get_memory_store
from src.fitme.services.user_service import UserService

# 数据库 users/health_metrics/user_settings 中已落库的字段，不应在记忆里重复记录
_GOAL_LABELS = {
    "lose_fat": "减脂",
    "gain_muscle": "增肌",
    "maintain": "保持健康",
    "improve_health": "改善体质",
}
_GENDER_LABELS = {"male": "男", "female": "女", "other": "其他"}


async def _db_profile_facts(user_id: str) -> list[tuple[str, str]]:
    """从数据库用户档案提取已落库的 (关键字, 值) 事实。

    关键字为空表示精确值匹配（如目标标签、昵称）；
    关键字非空表示需同时命中关键字与值（如身高/体重/年龄），避免误伤含数字的普通描述。
    任何异常都返回空列表，不阻断正常保存。
    """
    try:
        async with async_session_factory() as db:
            profile = await UserService.get_profile_summary(db, UUID(str(user_id)))
    except Exception:
        return []

    facts: list[tuple[str, str]] = []
    goal = profile.get("goal")
    if goal:
        label = _GOAL_LABELS.get(goal, goal)
        facts.append((label, label))
    if profile.get("height_cm"):
        facts.append(("身高", f"{int(profile['height_cm'])}"))
    if profile.get("weight_kg"):
        facts.append(("体重", f"{int(profile['weight_kg'])}"))
    if profile.get("age"):
        facts.append(("岁", f"{profile['age']}"))
    if profile.get("gender"):
        gender = _GENDER_LABELS.get(profile["gender"], profile["gender"])
        if len(gender) >= 2:
            facts.append(("", gender))
    if profile.get("name"):
        facts.append(("", profile["name"]))
    return facts


def _overlaps_db(text: str, db_facts: list[tuple[str, str]]) -> bool:
    """判断待保存文本是否命中某个数据库已落库的事实。

    带关键字的事实需同时命中关键字与值（如「身高1"75」）；无关键字的事实做子串双向匹配。
    """
    for keyword, value in db_facts:
        if not value or len(value) < 2:
            continue
        if keyword:
            if keyword in text and value in text:
                return True
        elif value in text or text in value:
            return True
    return False


async def _already_in_memory(
    store: MemoryStore, user_id: str, category: str, text: str
) -> bool:
    """判断同分类记忆中是否已存在内容相同/包含的记忆，避免近重复。"""
    try:
        rows = await store.retrieve_semantic(user_id, category=category, limit=50)
    except Exception:
        return False
    for mem in rows:
        obj = mem.object or ""
        if text in obj or (obj and obj in text):
            return True
    return False


@tool
async def recall_memory(
    user_id: str,
    query: str,
    memory_type: str = "all",
    top_k: int = 5,
) -> str:
    """
    回忆与查询相关的记忆。
    
    当需要回忆用户过去说过的话、做过的事、表达过的偏好时使用此工具。
    
    Args:
        user_id: 用户ID
        query: 要回忆的内容关键词或描述
        memory_type: 记忆类型，可选值：
            - "episodic": 只搜索经历/事件记忆
            - "semantic": 只搜索事实/偏好记忆
            - "procedural": 只搜索技能/流程记忆
            - "all": 搜索所有类型（默认）
        top_k: 返回的最大记忆数量
        
    Returns:
        相关记忆内容，如果没有找到则返回提示信息
    """
    store = get_memory_store()
    results = []
    
    # 检索情景记忆
    if memory_type in ("episodic", "all"):
        try:
            episodic = await store.retrieve_episodic(
                user_id=user_id,
                query=query,
                top_k=top_k,
            )
            for mem in episodic:
                time_str = mem.timestamp.strftime("%Y-%m-%d %H:%M") if mem.timestamp else "未知时间"
                summary = mem.summary or mem.content[:150]
                results.append(f"[经历 {time_str}] {summary}")
        except Exception as e:
            results.append(f"[检索情景记忆失败: {e}]")
    
    # 检索语义记忆
    if memory_type in ("semantic", "all"):
        try:
            semantic = await store.search_semantic(
                user_id=user_id,
                query=query,
                top_k=top_k,
            )
            for mem in semantic:
                results.append(f"[信息] {mem.subject} {mem.predicate} {mem.object}")
        except Exception as e:
            results.append(f"[检索语义记忆失败: {e}]")
    
    # 检索程序性记忆
    if memory_type in ("procedural", "all"):
        try:
            procedural = await store.retrieve_procedural(
                user_id=user_id,
                query=query,
                top_k=min(top_k, 3),
            )
            for mem in procedural:
                steps_str = ", ".join([s.get("action", "") for s in mem.steps[:3]])
                results.append(f"[技能] {mem.name}: {steps_str}")
        except Exception as e:
            results.append(f"[检索程序性记忆失败: {e}]")
    
    if not results:
        return f"没有找到与「{query}」相关的记忆。"
    
    return f"找到 {len(results)} 条相关记忆：\n" + "\n".join(results)


@tool
async def save_preference(
    user_id: str,
    preference: str,
    value: str,
) -> str:
    """
    保存用户偏好。
    
    当用户明确表达某个偏好时使用此工具，例如：
    - "我喜欢晨跑" -> preference="运动时间", value="晨跑"
    - "我不吃辣" -> preference="饮食禁忌", value="不吃辣"
    
    Args:
        user_id: 用户ID
        preference: 偏好类别（如"运动时间"、"饮食偏好"、"健身目标"）
        value: 具体偏好值
        
    Returns:
        保存结果确认
    """
    store = get_memory_store()
    value_text = f"{preference}: {value}"
    if await _already_in_memory(store, user_id, "preference", value_text):
        return f"该偏好已记录：{preference} = {value}"

    # 目标/身高/体重/年龄/性别等已在数据库落库的，不在记忆中重复保存
    db_facts = await _db_profile_facts(user_id)
    if _overlaps_db(value, db_facts):
        return "该信息已在数据库档案中记录，无需在记忆中重复保存。"

    try:
        await store.store_semantic(
            user_id=user_id,
            subject="用户",
            predicate="偏好",
            object=value_text,
            category="preference",
        )
        return f"已保存偏好：{preference} = {value}"
    except Exception as e:
        return f"保存偏好失败：{e}"


@tool
async def save_user_fact(
    user_id: str,
    subject: str,
    fact: str,
    category: str = "fact",
) -> str:
    """
    保存用户相关事实。
    
    当获知用户的重要信息时使用此工具，例如：
    - 身体状况："膝盖有旧伤"
    - 健身目标："减脂10斤"
    - 运动习惯："每周跑步3次"
    
    Args:
        user_id: 用户ID
        subject: 事实主体（通常是"用户"或具体部位如"膝盖"）
        fact: 事实内容
        category: 分类，可选值：
            - "fact": 一般事实（默认）
            - "status": 状态信息
            - "rule": 规则/约束
            - "preference": 偏好
        
    Returns:
        保存结果确认
    """
    store = get_memory_store()
    if await _already_in_memory(store, user_id, category, fact):
        return f"该信息已记录：{subject} - {fact}"

    # 目标/身高/体重/年龄/性别等已在数据库落库的，不在记忆中重复保存
    if category in ("fact", "status", "rule"):
        db_facts = await _db_profile_facts(user_id)
        if _overlaps_db(fact, db_facts):
            return "该信息已在数据库档案中记录，无需在记忆中重复保存。"

    try:
        await store.store_semantic(
            user_id=user_id,
            subject=subject,
            predicate="是",
            object=fact,
            category=category,
        )
        return f"已保存信息：{subject} - {fact}"
    except Exception as e:
        return f"保存信息失败：{e}"


@tool
async def list_user_profile(
    user_id: str,
    category: Optional[str] = None,
) -> str:
    """
    列出用户画像信息。
    
    查看已存储的用户偏好、事实、规则等信息。
    
    Args:
        user_id: 用户ID
        category: 可选的分类过滤：
            - "preference": 只看偏好
            - "fact": 只看事实
            - "status": 只看状态
            - None: 查看全部（默认）
        
    Returns:
        用户画像信息列表
    """
    store = get_memory_store()
    try:
        memories = await store.retrieve_semantic(
            user_id=user_id,
            category=category,
            limit=20,
        )
        
        if not memories:
            return "暂无存储的用户信息。"
        
        lines = [f"用户画像（共 {len(memories)} 条）："]
        for mem in memories:
            lines.append(f"- [{mem.category}] {mem.subject} {mem.predicate} {mem.object}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"获取用户信息失败：{e}"


@tool
async def save_event(
    user_id: str,
    event: str,
    importance: float = 0.5,
) -> str:
    """
    保存重要事件。
    
    当用户分享重要经历或事件时使用此工具。
    
    Args:
        user_id: 用户ID
        event: 事件描述
        importance: 重要性评分 (0-1)，默认0.5
        
    Returns:
        保存结果确认
    """
    store = get_memory_store()
    try:
        await store.store_episodic(
            user_id=user_id,
            content=event,
            memory_type="event",
            importance_score=importance,
        )
        return f"已记录事件：{event[:50]}..."
    except Exception as e:
        return f"记录事件失败：{e}"


def create_memory_tools() -> list:
    """
    创建所有记忆工具
    
    Returns:
        工具列表
    """
    return [
        recall_memory,
        save_preference,
        save_user_fact,
        list_user_profile,
        save_event,
    ]