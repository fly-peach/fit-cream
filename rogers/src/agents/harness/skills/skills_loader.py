"""
Skill 加载器

扫描 harness/skills/<name>/SKILL.md，解析 YAML frontmatter（name/description），
缓存正文供 skill_load_tool 按需读取。

SKILL.md 格式：

    ---
    name: plan-creation
    description: 用户大规模设计/调整训练或饮食计划时使用
    ---

    # Plan Creation Skill

    正文内容...

渐进式披露：
- L1 元数据（name+description）：agent_factory 构建时拼入 system_prompt
- L2 指令（正文）：AI 调 skill_load_tool 懒加载
- L3 资源（references/）：skill_load_tool 传 resource_path 按需读
"""

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger("fitcream.skills")

_SKILLS_DIR = Path(__file__).parent

# 最近一次技能加载的诊断信息（警告 / 错误），供 agent_factory 启动时打印
_skill_diagnostics: list[dict] = []

# skill 命名规范：小写字母 / 数字 / 连字符（对齐工具名风格）
_SKILL_NAME_RE = re.compile(r"^[a-z0-9-]+$")


def _xml_escape(text: str) -> str:
    """对技能元数据做 XML 转义，防止特殊字符破坏提示词 / 注入。"""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _parse_frontmatter(raw: str) -> tuple[str, str, str]:
    """解析 YAML frontmatter，返回 (name, description, body)。

    frontmatter 用 ``---`` 分隔，body 为分隔后的正文。
    优先用 pyyaml 解析；未安装时回退到简易 key-value 解析。
    """
    name = ""
    description = ""
    body = raw

    if not raw.startswith("---"):
        return name, description, body

    parts = raw.split("---", 2)
    if len(parts) < 3:
        return name, description, body

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    try:
        import yaml

        frontmatter = yaml.safe_load(frontmatter_text) or {}
        if isinstance(frontmatter, dict):
            name = str(frontmatter.get("name", ""))
            description = str(frontmatter.get("description", ""))
    except ImportError:
        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip("\"'")
    except Exception as e:
        logger.warning("Failed to parse skill frontmatter: %s", e)

    return name, description, body


@lru_cache(maxsize=1)
def _load_skills() -> dict[str, dict]:
    """扫描并加载所有 skill 元数据 + 正文。

    加载过程中的警告 / 错误写入模块级 ``_skill_diagnostics``，
    供 ``get_skill_diagnostics()`` 在 agent_factory 启动时打印。

    Returns:
        ``{skill_name: {"description": str, "body": str, "dir": Path}}``
    """
    global _skill_diagnostics
    skills: dict[str, dict] = {}
    diagnostics: list[dict] = []

    if not _SKILLS_DIR.is_dir():
        _skill_diagnostics = diagnostics
        return skills

    for entry in sorted(_SKILLS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("__"):
            continue

        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue

        try:
            raw = skill_md.read_text(encoding="utf-8")
            name, description, body = _parse_frontmatter(raw)
            if not name:
                name = entry.name
            if not _SKILL_NAME_RE.match(name):
                diagnostics.append(
                    {
                        "skill": entry.name,
                        "level": "warning",
                        "message": f"skill 名 '{name}' 不符合命名规范 ^[a-z0-9-]+$",
                    }
                )
                logger.warning("Skill name '%s' violates ^[a-z0-9-]+$", name)
            if not description:
                diagnostics.append(
                    {
                        "skill": name,
                        "level": "warning",
                        "message": "skill 缺少 description，catalog 中标为（无描述）",
                    }
                )
                logger.warning("Skill %s missing description, catalog marked as (无描述)", name)
            skills[name] = {
                "description": description,
                "body": body,
                "dir": entry,
            }
            logger.debug("Loaded skill: %s", name)
        except Exception as e:
            diagnostics.append(
                {
                    "skill": entry.name,
                    "level": "error",
                    "message": f"加载失败: {e}",
                }
            )
            logger.warning("Failed to load skill %s: %s", entry.name, e)

    _skill_diagnostics = diagnostics
    logger.info("Skills loaded: %d skill(s)", len(skills))
    return skills


def reload_skills() -> None:
    """清除缓存，重新扫描技能目录（开发调试用）。"""
    _load_skills.cache_clear()


def get_skill_diagnostics() -> list[dict]:
    """返回最近一次技能加载的诊断列表（skill / level / message），供启动时打印。

    确保先触发一次加载（首次或 reload_skills 清缓存后），返回该次扫描的诊断。
    无诊断返回空列表；调用方可直接 ``logger.warning`` 逐条输出。
    """
    _load_skills()
    return list(_skill_diagnostics)


def get_skill_catalog() -> list[dict[str, str]]:
    """返回技能目录（L1 元数据），供 system_prompt 注入。

    Returns:
        ``[{"name": str, "description": str}, ...]``
    """
    skills = _load_skills()
    return [
        {"name": name, "description": data["description"]}
        for name, data in sorted(skills.items())
    ]


def get_catalog_prompt() -> str:
    """构建「可用技能」系统提示词段（仅 name+description，控制 <500 token）。

    输出为 XML ``<available_skills>`` 块，name/description 均做 XML 转义，
    防止技能描述中的特殊字符破坏提示词或造成注入。

    无技能时返回空字符串。
    """
    catalog = get_skill_catalog()
    if not catalog:
        return ""

    lines = [
        "# 可用技能",
        "",
        "以下是可按需加载的技能。需要某个技能的完整指令时，调用 skill_load_tool 加载。",
        "<available_skills>",
    ]
    for skill in catalog:
        name = _xml_escape(skill["name"])
        desc = _xml_escape(skill["description"] or "（无描述）")
        lines.append(f"  <skill><name>{name}</name><description>{desc}</description></skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)


def get_skill_body(name: str) -> Optional[str]:
    """获取技能正文（L2 指令），未找到返回 None。"""
    data = _load_skills().get(name)
    return data["body"] if data else None


def get_skill_resource(name: str, resource_path: str) -> Optional[str]:
    """获取技能资源文件（L3 资源），未找到返回 None。

    resource_path 为相对技能目录的路径（如 ``references/foo.md``）。
    防路径穿越：目标必须在技能目录内。
    """
    data = _load_skills().get(name)
    if not data:
        return None

    base_dir: Path = data["dir"]
    target = (base_dir / resource_path).resolve()

    try:
        target.relative_to(base_dir.resolve())
    except ValueError:
        logger.warning("Path traversal blocked: %s/%s", name, resource_path)
        return None

    if not target.is_file():
        return None

    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        logger.warning("Failed to read resource %s/%s: %s", name, resource_path, e)
        return None
