"""
FitCream Agent Prompts

导出所有 prompt 模板，供 agent_graph 和其他模块使用。
"""

from agents.harness.prompts.system import (
    SYSTEM_PROMPT,
    build_system_prompt,
    IDENTITY_SECTION,
    CAPABILITIES_SECTION,
    BEHAVIOR_RULES_SECTION,
    OUTPUT_FORMAT_SECTION,
    CONSTRAINTS_SECTION,
    EXAMPLES_SECTION,
)

__all__ = [
    "SYSTEM_PROMPT",
    "build_system_prompt",
    "IDENTITY_SECTION",
    "CAPABILITIES_SECTION",
    "BEHAVIOR_RULES_SECTION",
    "OUTPUT_FORMAT_SECTION",
    "CONSTRAINTS_SECTION",
    "EXAMPLES_SECTION",
]