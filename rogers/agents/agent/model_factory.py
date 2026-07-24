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
from typing import Any, Optional, Iterator, AsyncIterator

from typing import cast

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessageChunk, ToolCallChunk
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGenerationChunk, ChatResult

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def _get_setting(key: str, default: str = "") -> str:
    try:
        from app.config import settings
        return str(getattr(settings, key, default))
    except Exception:
        return os.getenv(key, default)


DEFAULT_MODEL = _get_setting("DASHSCOPE_MODEL", "qwen3.5-flash")

# 视觉模型备选（当主模型不支持图片识别时，可切换到 Qwen-VL 系列）
DEFAULT_VISION_MODEL = _get_setting("DASHSCOPE_VISION_MODEL", "qwen3-vl-flash")


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
        kwargs.setdefault("api_key", _get_setting("DASHSCOPE_API_KEY"))

        super().__init__(**kwargs)

    def _create_chat_result(
        self, response: Any, generation_info: Optional[dict] = None
    ) -> ChatResult:
        # 调用父类方法创建标准结果，再补充 reasoning_content
        result = super()._create_chat_result(response, generation_info)

        # 从原始响应中提取 reasoning_content（langchain-openai 会丢弃此字段）
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
        # 直接拦截原始 OpenAI stream，确保 delta 中的 reasoning_content 被正确捕获
        # （langchain-openai >= 1.3 会丢弃 delta 中的未知字段）
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
        # 异步版本：同样拦截原始 stream 以捕获 reasoning_content
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
        # 将 LangChain 消息对象转换为 OpenAI API 格式的 dict
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

        # 传递 tools 参数（bind_tools 注入的 function calling 定义）
        tools = kwargs.get("tools")
        if tools:
            params["tools"] = tools
        tool_choice = kwargs.get("tool_choice")
        if tool_choice:
            params["tool_choice"] = tool_choice

        return params

    def _convert_messages_to_dicts(self, messages: list[BaseMessage]) -> list[dict]:
        """
        将 LangChain 消息对象转换为 OpenAI API 格式的 dict。

        支持多模态内容：当 message.content 为 list 时（包含 text/image_url 等
        content blocks），_convert_message_to_dict 会将其转换为 OpenAI 兼容格式，
        DashScope Qwen-VL 接口可直接处理。
        """
        from langchain_openai.chat_models.base import _convert_message_to_dict
        return [_convert_message_to_dict(m) for m in messages]

    def _convert_raw_chunk(self, raw_chunk: Any) -> Optional[ChatGenerationChunk]:
        # 提取 usage 信息（流式最后一个 chunk 的 usage 在 raw_chunk 顶层）
        raw_usage = getattr(raw_chunk, "usage", None)
        usage_metadata: UsageMetadata | None = None
        if raw_usage:
            usage_metadata = cast(UsageMetadata, {
                "input_tokens": getattr(raw_usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(raw_usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(raw_usage, "total_tokens", 0) or 0,
            })

        if not raw_chunk.choices:
            # 流式最后一个 chunk 可能只有 usage 没有 choices
            if usage_metadata:
                return ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        usage_metadata=usage_metadata,
                    ),
                    text="",
                )
            return None

        delta = raw_chunk.choices[0].delta
        if delta is None:
            if usage_metadata:
                return ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        usage_metadata=usage_metadata,
                    ),
                    text="",
                )
            return None

        content = delta.content or ""
        reasoning_content = getattr(delta, "reasoning_content", None)

        additional_kwargs: dict[str, Any] = {}
        if reasoning_content:
            additional_kwargs["reasoning_content"] = reasoning_content

        # 构建 tool_call_chunks（LangGraph ReAct agent 需要此字段来解析工具调用）
        tool_call_chunks: list[ToolCallChunk] = []
        if delta.tool_calls:
            for tc in delta.tool_calls:
                tool_call_chunks.append(
                    ToolCallChunk(
                        name=tc.function.name if tc.function else None,
                        args=tc.function.arguments if tc.function else "",
                        id=tc.id,
                        index=tc.index,
                    )
                )

        if not content and not reasoning_content and not delta.tool_calls:
            if delta.role or usage_metadata:
                return ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="",
                        additional_kwargs=additional_kwargs,
                        tool_call_chunks=tool_call_chunks,
                        response_metadata={"role": delta.role} if delta.role else {},
                        usage_metadata=usage_metadata,
                    ),
                    text="",
                )
            return None

        chunk = ChatGenerationChunk(
            message=AIMessageChunk(
                content=content,
                additional_kwargs=additional_kwargs,
                tool_call_chunks=tool_call_chunks,
                usage_metadata=usage_metadata,
            ),
            text=content,
        )
        return chunk


def create_chat_dashscope(
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    enable_thinking: Optional[bool] = None,
    streaming: bool = False,
    **kwargs: Any,
) -> ChatDashScope:
    """
    工厂函数：创建配置好的 ChatDashScope 实例。

    默认值从 .env 配置读取（DASHSCOPE_MODEL / DASHSCOPE_TEMPERATURE / DASHSCOPE_ENABLE_THINKING）。

    Args:
        model: 模型名称，默认从 DASHSCOPE_MODEL 读取
        temperature: 温度参数，默认从 DASHSCOPE_TEMPERATURE 读取
        enable_thinking: 是否启用思考模式，默认从 DASHSCOPE_ENABLE_THINKING 读取
        streaming: 是否默认流式，默认 False
        **kwargs: 传递给 ChatOpenAI 的其他参数

    Returns:
        ChatDashScope 实例
    """
    return ChatDashScope(
        model=model or DEFAULT_MODEL,
        temperature=temperature if temperature is not None else float(_get_setting("DASHSCOPE_TEMPERATURE", "1.2")),
        enable_thinking=enable_thinking if enable_thinking is not None else _get_setting("DASHSCOPE_ENABLE_THINKING", "true").lower() == "true",
        streaming=streaming,
        stream_usage=True,
        **kwargs,
    )
