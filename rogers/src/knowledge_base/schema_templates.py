"""
实体类型模板（纯逻辑，零 DB 依赖）

参考 LLM Wiki 的 ENTITY_TYPES，定义健身领域的实体模板。
用于创建文档时生成 frontmatter + 章节骨架。
"""
from __future__ import annotations

ENTITY_TYPES: dict[str, dict] = {
    "exercise": {
        "label": "训练动作",
        "frontmatter": {
            "type": "exercise",
            "title": "",
            "tags": [],
            "muscle_group": "",
            "equipment": "",
        },
        "sections": ["## 动作要领", "## 目标肌群", "## 常见错误", "## 变式"],
    },
    "nutrition": {
        "label": "营养知识",
        "frontmatter": {
            "type": "nutrition",
            "title": "",
            "tags": [],
            "category": "",
        },
        "sections": ["## 营养成分", "## 食物来源", "## 摄入建议"],
    },
    "plan_template": {
        "label": "计划模板",
        "frontmatter": {
            "type": "plan_template",
            "title": "",
            "tags": [],
            "goal": "",
            "difficulty": "",
        },
        "sections": ["## 训练目标", "## 周计划", "## 注意事项"],
    },
    "concept": {
        "label": "健身概念",
        "frontmatter": {
            "type": "concept",
            "title": "",
            "tags": [],
        },
        "sections": ["## 定义", "## 原理", "## 应用", "## 相关概念"],
    },
}


def get_template(entity_type: str) -> str:
    """获取指定实体类型的 Markdown 模板（含 frontmatter + 章节骨架）"""
    tmpl = ENTITY_TYPES.get(entity_type)
    if not tmpl:
        return ""

    lines = ["---"]
    fm = tmpl["frontmatter"]
    for key, val in fm.items():
        if isinstance(val, list):
            lines.append(f"{key}: []")
        elif val:
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: ")
    lines.append("---")
    lines.append("")
    lines.append(f"# {fm.get('title') or tmpl['label']}")
    lines.append("")
    for section in tmpl["sections"]:
        lines.append(section)
        lines.append("")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def list_entity_types() -> list[dict]:
    """列出所有实体类型及标签"""
    return [{"type": k, "label": v["label"]} for k, v in ENTITY_TYPES.items()]
