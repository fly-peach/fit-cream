"""
FitCream Skill 子系统

渐进式披露（仿 Deep Agents）：
- L1 元数据（name+description）：agent_factory 构建时注入 system_prompt（<500 token）
- L2 指令（SKILL.md 正文）：AI 按描述调 skill_load_tool 懒加载
- L3 资源（references/）：skill_load_tool 传 resource_path 按需读

目录结构：
    harness/skills/
    ├── __init__.py          本文件
    ├── skills_loader.py     加载器：扫描 SKILL.md、解析 frontmatter、缓存正文
    └── <skill-name>/        每个技能一个子目录
        ├── SKILL.md         技能定义（YAML frontmatter + markdown 正文）
        └── references/      可选资源文件
"""

from src.agents.harness.skills.skills_loader import (
    get_catalog_prompt,
    get_skill_body,
    get_skill_catalog,
    get_skill_resource,
    reload_skills,
)

__all__ = [
    "get_skill_catalog",
    "get_skill_body",
    "get_skill_resource",
    "get_catalog_prompt",
    "reload_skills",
]
