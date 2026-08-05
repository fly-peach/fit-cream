"""
FitCream Agent Prompts

导出所有 prompt 模板，供 agent_graph 和其他模块使用。
"""

from src.agents.harness.orchestration.prompts.system import (
    SYSTEM_PROMPT,
    BASE_SYSTEM_PROMPT,
    INTENT_PROMPTS,
    INTENT_KEYWORDS,
    build_system_prompt,
)

__all__ = [
    "SYSTEM_PROMPT",
    "BASE_SYSTEM_PROMPT",
    "INTENT_PROMPTS",
    "INTENT_KEYWORDS",
    "build_system_prompt",
]
