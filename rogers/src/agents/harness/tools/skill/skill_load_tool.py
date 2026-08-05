"""
Skill 加载工具

供 Agent 按需懒加载技能指令（L2）或技能资源（L3）。
渐进式披露：catalog（L1）已静态烘焙进 system_prompt，
正文需 AI 调用本工具读取。
"""

from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.skills.skills_loader import (
    get_skill_body,
    get_skill_catalog,
    get_skill_resource,
)


class SkillLoadInput(BaseModel):
    """加载技能指令的输入参数"""

    skill_name: str = Field(description="要加载的技能名称（见系统提示词「可用技能」目录）")
    resource_path: Optional[str] = Field(
        default=None,
        description="技能资源文件的相对路径（如 references/foo.md）。不传则加载 SKILL.md 正文。",
    )


@tool(args_schema=SkillLoadInput)
async def skill_load_tool(
    skill_name: str,
    resource_path: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    加载技能的详细指令正文或资源文件。

    使用场景：
    - 系统提示词列出了可用技能的名称和简介，你需要某个技能的完整指令时调用此工具
    - 传入 skill_name 加载 SKILL.md 正文
    - 传入 resource_path 加载该技能目录下的资源文件

    Returns:
        技能正文或资源文件内容
    """
    if resource_path:
        content = get_skill_resource(skill_name, resource_path)
        if content is None:
            available = [s["name"] for s in get_skill_catalog()]
            return {
                "success": False,
                "error": f"未找到技能 {skill_name} 的资源文件 {resource_path}",
                "available_skills": available,
            }
        return {"success": True, "content": content, "source": f"{skill_name}/{resource_path}"}

    body = get_skill_body(skill_name)
    if body is None:
        available = [s["name"] for s in get_skill_catalog()]
        return {
            "success": False,
            "error": f"未找到技能 {skill_name}",
            "available_skills": available,
        }
    return {"success": True, "content": body, "skill_name": skill_name}
