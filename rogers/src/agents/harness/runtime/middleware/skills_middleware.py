"""
Skills 中间件

将技能目录（name+description）静态烘焙进 system_prompt，
不在每轮 before_model 重复注入（省 token）。

技能正文由 skill_load_tool 按需懒加载（渐进式披露 L2）。
"""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langgraph.runtime import Runtime


class SkillsMiddleware(AgentMiddleware):
    """
    Skills 中间件 - 技能目录静态管理。

    职责：
    - catalog（name+description）在 agent_factory 构建时已拼入 system_prompt
    - before_model 不重复注入（避免每轮 token 浪费）
    - 技能正文由 skill_load_tool 懒加载

    无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
    """

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        """catalog 已烘焙进 system_prompt，无需每轮注入。"""
        return None
