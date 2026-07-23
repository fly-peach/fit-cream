"""
记忆工具 (Memory Tools)

提供给 Agent 使用的记忆相关工具：
- recall_memory: 检索相关记忆
- save_memory: 保存记忆
- save_preference: 保存用户偏好
- list_user_facts: 列出用户信息

用法：
    from agents.memory.tools import create_memory_tools
    
    tools = create_memory_tools()
    agent = create_react_agent(llm, tools=tools)
"""

from typing import Optional
from langchain_core.tools import tool

from agents.memory.store import get_memory_store


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
    try:
        await store.store_semantic(
            user_id=user_id,
            subject="用户",
            predicate="偏好",
            object=f"{preference}: {value}",
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