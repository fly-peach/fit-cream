"""
记忆工具 (Memory Tools)

提供给 Agent 使用的记忆相关工具：
- recall_memory: 检索相关记忆（情景/语义/程序性，返回带 id）
- save_preference: 保存用户偏好（predicate=偏好类别，同类别新值自动覆盖旧值）
- save_user_fact: 保存用户事实（可指定 predicate 区分）
- list_user_profile: 列出用户画像信息
- save_event: 记录重要事件
- update_memory: 按 id 更新一条记忆（用户推翻/修订旧记忆时使用）
- delete_memory: 按 id 删除一条记忆

用法：
    from src.agents.harness.tools.memory.memory_tools import create_memory_tools

    tools = create_memory_tools()
    agent = create_react_agent(llm, tools=tools)
"""

from typing import Optional
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.database import async_session_factory
from src.agents.harness.runtime.memory.store import MemoryStore, get_memory_store
from src.agents.harness.tools._common import extract_user_id
from src.fitme.services.user_service import UserService


def _resolve_user_id(config: Optional[RunnableConfig]) -> Optional[str]:
    """从认证 RunnableConfig 解析当前用户 ID（字符串形式，供 MemoryStore 使用）。

    与 fitme/knowledge 工具一致：身份取自 config.configurable.user_id（由 HTTP 层
    注入），而非 LLM 自行传入，杜绝跨用户读写他人记忆。
    """
    uid = extract_user_id(config)
    return str(uid) if uid else None

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
    store: MemoryStore,
    user_id: str,
    category: str,
    text: str,
    predicate: Optional[str] = None,
) -> bool:
    """判断同分类记忆中是否已存在相同 predicate 且内容相同/包含的记忆，避免近重复。"""
    try:
        rows = await store.retrieve_semantic(user_id, category=category, limit=50)
    except Exception:
        return False
    for mem in rows:
        if predicate is not None and mem.predicate != predicate:
            continue
        obj = mem.object or ""
        if text in obj or (obj and obj in text):
            return True
    return False


@tool
async def recall_memory(
    query: str,
    memory_type: str = "all",
    top_k: int = 5,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    回忆与查询相关的记忆。
    
    当需要回忆用户过去说过的话、做过的事、表达过的偏好时使用此工具。
    
    Args:
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
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
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
                results.append(f"[经历 {time_str} | id:{mem.id}] {summary}")
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
                results.append(f"[信息 id:{mem.id}] {mem.subject} {mem.predicate} {mem.object}")
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
                results.append(f"[技能 id:{mem.id}] {mem.name}: {steps_str}")
        except Exception as e:
            results.append(f"[检索程序性记忆失败: {e}]")
    
    if not results:
        return f"没有找到与「{query}」相关的记忆。"
    
    return f"找到 {len(results)} 条相关记忆：\n" + "\n".join(results)


@tool
async def save_preference(
    preference: str,
    value: str,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    保存用户偏好。
    
    当用户明确表达某个偏好时使用此工具，例如：
    - "我喜欢晨跑" -> preference="运动时间", value="晨跑"
    - "我不吃辣" -> preference="饮食禁忌", value="不吃辣"
    
    Args:
        preference: 偏好类别（如"运动时间"、"饮食偏好"、"健身目标"）
        value: 具体偏好值
        
    Returns:
        保存结果确认
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
    store = get_memory_store()
    if await _already_in_memory(store, user_id, "preference", value, predicate=preference):
        return f"该偏好已记录：{preference} = {value}"

    # 目标/身高/体重/年龄/性别等已在数据库落库的，不在记忆中重复保存
    db_facts = await _db_profile_facts(user_id)
    if _overlaps_db(value, db_facts):
        return "该信息已在数据库档案中记录，无需在记忆中重复保存。"

    try:
        await store.store_semantic(
            user_id=user_id,
            subject="用户",
            predicate=preference,
            object=value,
            category="preference",
        )
        return f"已保存偏好：{preference} = {value}"
    except Exception as e:
        return f"保存偏好失败：{e}"


@tool
async def save_user_fact(
    subject: str,
    fact: str,
    category: str = "fact",
    predicate: str = "是",
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    保存用户相关事实。
    
    当获知用户的重要信息时使用此工具，例如：
    - 身体状况："膝盖有旧伤"
    - 健身目标："减脂10斤"
    - 运动习惯："每周跑步3次"
    
    Args:
        subject: 事实主体（通常是"用户"或具体部位如"膝盖"）
        fact: 事实内容
        category: 分类，可选值：
            - "fact": 一般事实（默认）
            - "status": 状态信息
            - "rule": 规则/约束
            - "preference": 偏好
        predicate: 关系谓词，用于区分不同类事实（默认"是"）。
            同类话题应使用相同的 predicate，以便同 (subject, predicate) 自动更新旧值。
            （保存偏好时推荐改用 save_preference，predicate 即偏好类别）
        
    Returns:
        保存结果确认
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
    store = get_memory_store()
    if await _already_in_memory(store, user_id, category, fact, predicate=predicate):
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
            predicate=predicate,
            object=fact,
            category=category,
        )
        return f"已保存信息：{subject} - {fact}"
    except Exception as e:
        return f"保存信息失败：{e}"


@tool
async def list_user_profile(
    category: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    列出用户画像信息。
    
    查看已存储的用户偏好、事实、规则等信息。
    
    Args:
        category: 可选的分类过滤：
            - "preference": 只看偏好
            - "fact": 只看事实
            - "status": 只看状态
            - None: 查看全部（默认）
        
    Returns:
        用户画像信息列表
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
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
    event: str,
    importance: float = 0.5,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    保存重要事件。
    
    当用户分享重要经历或事件时使用此工具。
    
    Args:
        event: 事件描述
        importance: 重要性评分 (0-1)，默认0.5
        
    Returns:
        保存结果确认
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
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


@tool
async def update_memory(
    memory_id: str,
    new_value: str,
    memory_type: str = "semantic",
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    更新一条已存在的记忆（按记忆 id）。

    当用户推翻或修订之前记录的偏好/事实时使用，例如此前记录"喜欢冰淇淋"，
    今天更正为"更喜欢炸鸡"。用 recall_memory 找到待修订记忆的 id 后传入。

    Args:
        memory_id: 要更新的记忆 id（recall_memory 返回的 id:xxx）
        new_value: 新的记忆内容
        memory_type: 记忆类型，可选值：
            - "semantic": 语义记忆/偏好/事实（默认）
            - "episodic": 情景/经历记忆

    Returns:
        更新结果确认
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
    store = get_memory_store()
    try:
        mid = UUID(memory_id)
    except (ValueError, TypeError):
        return f"无效的记忆ID：{memory_id}"

    try:
        if memory_type == "semantic":
            ok = await store.update_semantic(user_id, mid, object=new_value)
        elif memory_type == "episodic":
            ok = await store.update_episodic(user_id, mid, content=new_value)
        else:
            return f"不支持的记忆类型：{memory_type}"
    except Exception as e:
        return f"更新记忆失败：{e}"

    if ok:
        return f"已更新记忆 {memory_id} 为：{new_value}"
    return f"未找到该记忆或无权修改：{memory_id}"


@tool
async def delete_memory(
    memory_id: str,
    memory_type: str = "semantic",
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> str:
    """
    删除一条记忆（按记忆 id）。

    当某条记忆已作废、错误或与用户最新说法冲突且不再需要时使用。
    用 recall_memory 找到待删除记忆的 id 后传入。

    Args:
        memory_id: 要删除的记忆 id（recall_memory 返回的 id:xxx）
        memory_type: 记忆类型，可选值：
            - "semantic": 语义记忆/偏好/事实（默认）
            - "episodic": 情景/经历记忆

    Returns:
        删除结果确认
    """
    user_id = _resolve_user_id(config)
    if not user_id:
        return "无法获取当前用户身份，操作未执行。"
    store = get_memory_store()
    try:
        mid = UUID(memory_id)
    except (ValueError, TypeError):
        return f"无效的记忆ID：{memory_id}"

    try:
        if memory_type == "semantic":
            ok = await store.delete_semantic(user_id, mid)
        elif memory_type == "episodic":
            ok = await store.delete_episodic(user_id, mid)
        else:
            return f"不支持的记忆类型：{memory_type}"
    except Exception as e:
        return f"删除记忆失败：{e}"

    if ok:
        return f"已删除记忆 {memory_id}"
    return f"未找到该记忆或无权删除：{memory_id}"


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
        update_memory,
        delete_memory,
    ]