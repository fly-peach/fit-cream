"""
提示词临时注入辅助（wrap_model_call 链内共享，F1 迁移）

背景：before_model 返回 {"messages": [SystemMessage(...)]} 会经 messages reducer
写入 state 并随 checkpointer 持久化——同一 thread 每轮 +1~4 条 SystemMessage 逐轮
累积（F1，token 膨胀 + 陈旧提示污染后续轮次）。迁移后 Intent / PlanQueue /
ContentValidation / KBGate 统一经本辅助把提示词合并进 request.system_message：
临时注入、不落 checkpoint、不污染消息历史；多个注入器在同一 wrap 链内按注册顺序
叠加（先注册者先合并、显示在最前）。

注意：只返回 override 后的新 request，绝不返回 state dict（wrap-style 若返回 dict
同样会经 reducer 持久化，与本迁移目标相悖）。

`request.system_message` 初始为 create_agent 的基础系统提示词（agent_factory 构建
时烘焙），此处把每轮一次性提示词追加在其后；模型执行时框架会把 system_message
前置拼回消息列表，注入内容照常对模型可见。
"""

from langchain_core.messages import SystemMessage


def merge_system_prompt(request, prompt: str):
    """把 prompt 追加合并进 request.system_message，返回 override 后的新 request。

    - request.system_message 为空时直接以 prompt 作为系统消息；
    - 非空时以 ``\\n\\n`` 拼接（基础系统提示词保持在最前）；
    - 返回新的 ModelRequest，原始 request 与 request.state 均不被改动。
    """
    existing = request.system_message
    if existing is None or not existing.content:
        new = SystemMessage(content=prompt)
    else:
        base = existing.content
        base_text = base if isinstance(base, str) else str(base)
        new = SystemMessage(content=f"{base_text}\n\n{prompt}")
    return request.override(system_message=new)
