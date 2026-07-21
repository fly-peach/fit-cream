"""
FitCream Agent 模块

基于 LangGraph 的 ReAct Agent，用于健身教练对话。

子模块：
- agent_graph: Agent 主入口（graph 变量，供 langgraph.json / FastAPI 使用）
- agent/: Agent 工厂（create_fitcream_agent）和模型工厂（ChatDashScope）
- harness/: 辅助组件（prompts / tools / middleware）

用法：
    from agents import graph, init_agent

    # FastAPI lifespan 中初始化（带 checkpointer）
    await init_agent()

    # 或直接使用默认 graph
    async for event in graph.astream_events(...):
        ...
"""

from agents.agent_graph import graph, init_agent

__all__ = ["graph", "init_agent"]
