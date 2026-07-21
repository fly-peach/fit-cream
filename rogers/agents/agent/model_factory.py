"""
DashScope 模型工厂

封装 ChatDashScope，支持提取 DashScope 模型的思考内容 (reasoning_content)。
基于 langchain-openai 的 ChatOpenAI，通过直接拦截原始 OpenAI stream 确保
reasoning_content 被正确捕获（langchain-openai >= 1.3 会丢弃 delta 中的未知字段）。

用法:
    from agents.agent.model_factory import create_chat_dashscope

    llm = create_chat_dashscope()
    response = llm.invoke([("human", "你好")])

    # 获取思考内容
    reasoning = response.additional_kwargs.get("reasoning_content", "")
    # 获取最终回答
    answer = response.content

    # 流式调用
    for chunk in llm.stream([("human", "你好")]):
        reasoning = chunk.additional_kwargs.get("reasoning_content", "")
        if reasoning:
            print(f"[思考] {reasoning}", end="")
        if chunk.content:
            print(chunk.content, end="")
"""

import os
from pathlib import Path
from typing import Any, Optional, Iterator, AsyncIterator

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult

_env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
load_dotenv(_env_path)

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.5-flash"


class ChatDashScope(ChatOpenAI):
    """
    DashScope 模型封装，继承 ChatOpenAI。

    核心功能：
    - 自动启用 enable_thinking 参数
    - 非流式：从原始响应中提取 reasoning_content 到 additional_kwargs
    - 流式：直接拦截原始 OpenAI stream，从 delta 中提取 reasoning_content

    提取后通过 response.additional_kwargs["reasoning_content"] 访问思考内容。
    """

    enable_thinking: bool = True

    def __init__(self, **kwargs: Any):
        extra_body = kwargs.pop("extra_body", None) or {}
        enable_thinking = kwargs.pop("enable_thinking", True)

        if enable_thinking:
            extra_body["enable_thinking"] = True

        kwargs["extra_body"] = extra_body
        kwargs["enable_thinking"] = enable_thinking

        kwargs.setdefault("base_url", DASHSCOPE_BASE_URL)
        kwargs.setdefault("model", DEFAULT_MODEL)
        kwargs.setdefault("api_key", os.getenv("DASHSCOPE_API_KEY"))

        super().__init__(**kwargs)

    def _create_chat_result(
        self, response: Any, generation_info: Optional[dict] = None
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)

        choices = getattr(response, "choices", None)
        if choices is None and isinstance(response, dict):
            choices = response.get("choices", [])

        if not choices:
            return result

        for i, gen in enumerate(result.generations):
            if i >= len(choices):
                break
            choice = choices[i]

            if isinstance(choice, dict):
                msg = choice.get("message", {})
                rc = msg.get("reasoning_content")
            else:
                msg = getattr(choice, "message", None)
                rc = getattr(msg, "reasoning_content", None) if msg else None

            if rc:
                gen.message.additional_kwargs["reasoning_content"] = rc

        return result

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        raw_stream = self._create_raw_stream(messages, stop, **kwargs)
        for raw_chunk in raw_stream:
            gen_chunk = self._convert_raw_chunk(raw_chunk)
            if gen_chunk is not None:
                if run_manager:
                    run_manager.on_llm_new_token(gen_chunk.text, chunk=gen_chunk)
                yield gen_chunk

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        raw_stream = await self._create_raw_astream(messages, stop, **kwargs)
        async for raw_chunk in raw_stream:
            gen_chunk = self._convert_raw_chunk(raw_chunk)
            if gen_chunk is not None:
                if run_manager:
                    await run_manager.on_llm_new_token(gen_chunk.text, chunk=gen_chunk)
                yield gen_chunk

    def _create_raw_stream(self, messages, stop, **kwargs):
        params = self._build_stream_params(messages, stop, **kwargs)
        return self.client.create(**params)

    async def _create_raw_astream(self, messages, stop, **kwargs):
        params = self._build_stream_params(messages, stop, **kwargs)
        return await self.async_client.create(**params)

    def _build_stream_params(self, messages, stop, **kwargs) -> dict:
        message_dicts = self._convert_messages_to_dicts(messages)
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": message_dicts,
            "stream": True,
        }
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if stop:
            params["stop"] = stop
        if self.max_tokens is not None:
            params["max_tokens"] = self.max_tokens
        if self.top_p is not None:
            params["top_p"] = self.top_p

        extra_body = self.extra_body or {}
        if extra_body:
            params["extra_body"] = extra_body

        if self.stream_usage:
            params["stream_options"] = {"include_usage": True}

        return params

    def _convert_messages_to_dicts(self, messages: list[BaseMessage]) -> list[dict]:
        from langchain_openai.chat_models.base import _convert_message_to_dict
        return [_convert_message_to_dict(m) for m in messages]

    def _convert_raw_chunk(self, raw_chunk: Any) -> Optional[ChatGenerationChunk]:
        if not raw_chunk.choices:
            return None

        delta = raw_chunk.choices[0].delta
        if delta is None:
            return None

        content = delta.content or ""
        reasoning_content = getattr(delta, "reasoning_content", None)

        additional_kwargs: dict[str, Any] = {}
        if reasoning_content:
            additional_kwargs["reasoning_content"] = reasoning_content

        if delta.tool_calls:
            additional_kwargs["tool_calls"] = [
                tc.model_dump() for tc in delta.tool_calls
            ]

        if not content and not reasoning_content and not delta.tool_calls:
            if delta.role:
                return ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        additional_kwargs=additional_kwargs,
                        response_metadata={"role": delta.role},
                    ),
                    text="",
                )
            return None

        chunk = ChatGenerationChunk(
            message=AIMessageChunk(
                content=content,
                additional_kwargs=additional_kwargs,
            ),
            text=content,
        )
        return chunk


def create_chat_dashscope(
    model: str = DEFAULT_MODEL,
    temperature: float = 1.2,
    enable_thinking: bool = True,
    streaming: bool = False,
    **kwargs: Any,
) -> ChatDashScope:
    """
    工厂函数：创建配置好的 ChatDashScope 实例。

    Args:
        model: 模型名称，默认 qwen3.5-flash
        temperature: 温度参数，默认 1.2（思考模式建议较高温度）
        enable_thinking: 是否启用思考模式，默认 True
        streaming: 是否默认流式，默认 False
        **kwargs: 传递给 ChatOpenAI 的其他参数

    Returns:
        ChatDashScope 实例
    """
    return ChatDashScope(
        model=model,
        temperature=temperature,
        enable_thinking=enable_thinking,
        streaming=streaming,
        **kwargs,
    )
