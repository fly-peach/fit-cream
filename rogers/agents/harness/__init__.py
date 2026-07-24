"""
Agent Harness 模块

包含 Agent 的辅助组件：
- prompts: System prompts 和模板
- tools: LangChain Tools 定义
- middleware: Agent 中间件（日志、限流）
- memory: 分层认知记忆架构（情景/语义/程序性记忆）
"""

from agents.harness.prompts import SYSTEM_PROMPT, build_system_prompt

__all__ = ["SYSTEM_PROMPT", "build_system_prompt"]