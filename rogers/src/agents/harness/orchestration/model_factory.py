"""
模型工厂（统一模型构建 + 用户自备 DeepSeek Key（BYOK）路由）

统一由官方集成构建模型，不再维护自研 ChatDashScope：
- qwen 侧：``langchain_qwq.ChatQwen``（DashScope 官方集成，原生处理
  ``enable_thinking`` / ``reasoning_content`` / ``stream_usage``）
- deepseek 侧：``ChatDeepSeekVision``（继承 ``langchain_deepseek.ChatDeepSeek``，
  补齐 vision-exp 的能力档案，官方端点 https://api.deepseek.com）

核心入口：
- ``resolve_chat_model(*, user_ds_key=None)``：按请求解析模型。有用户自备
  DeepSeek key 时走 deepseek 视觉模型（进程内 LRU 缓存 + 负缓存：某 key 曾
  401/403 则标记无效回退 qwen）；无 key 时走 qwen（``DASHSCOPE_MODEL``）。
- ``build_model(ModelSpec)``：按 spec.provider 分派构造（可配置驱动）。
- token 工具：``extract_usage``（对齐 LangChain UsageMetadata 标准，补
  cache_read / reasoning）与 ``estimate_tokens``（``count_tokens_approximately``，
  替换 ``output_chars//2`` 启发式）。

guarded import：生产环境未安装 ``langchain-qwq`` / ``langchain-deepseek`` 时，
对应工厂调用会抛 ImportError（不阻断本模块其余导出）。

用法:
    from src.agents.harness.orchestration.model_factory import resolve_chat_model

    llm = resolve_chat_model()                       # 无 key -> qwen
    llm = resolve_chat_model(user_ds_key=key)        # 有 key -> deepseek
"""

import hashlib
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.messages.utils import count_tokens_approximately

logger = logging.getLogger("fitcream.agent")

DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# DeepSeek 官方 API 端点（视觉模型 deepseek-v4-flash-vision-exp 仅此处提供）
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"


def _get_setting(key: str, default: str = "") -> str:
    try:
        from app.config import settings
        return str(getattr(settings, key, default))
    except Exception:
        import os
        return os.getenv(key, default)


# 默认统一为 qwen3.8-flash（多模态），不再区分文本/视觉模型切换
DEFAULT_MODEL = _get_setting("DASHSCOPE_MODEL", "qwen3.8-flash")

# DeepSeek 视觉模型（官方端点；DashScope 未托管，且 DashScope 上的 deepseek
# 文本模型收到 image_url 块会静默丢弃，不报错也不识图）
DEEPSEEK_VISION_MODEL_NAME = _get_setting(
    "DEEPSEEK_VISION_MODEL", "deepseek-v4-flash-vision-exp"
)


# ===== guarded imports（未安装时相应工厂抛 ImportError） =====

try:
    from langchain_qwq import ChatQwen

    _HAS_LANGCHAIN_QWQ = True
except ImportError:
    ChatQwen = None  # type: ignore[assignment, misc]
    _HAS_LANGCHAIN_QWQ = False

try:
    from langchain_deepseek import ChatDeepSeek as _ChatDeepSeekBase

    _HAS_LANGCHAIN_DEEPSEEK = True
except ImportError:
    _ChatDeepSeekBase = None  # type: ignore[assignment, misc]
    _HAS_LANGCHAIN_DEEPSEEK = False


# ===== ModelSpec（统一模型入参） =====


@dataclass
class ModelSpec:
    """统一的模型构建入参（与 provider 无关的公共字段）。"""

    provider: str = "qwen"  # "qwen" | "deepseek"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    enable_thinking: Optional[bool] = None
    max_tokens: Optional[int] = None
    stream_usage: bool = True
    timeout: Optional[float] = None
    max_retries: Optional[int] = None
    extra: dict[str, Any] = field(default_factory=dict)


def build_model(spec: ModelSpec) -> BaseChatModel:
    """按 ``spec.provider`` 分派构建模型（qwen / deepseek 官方集成）。"""
    if spec.provider == "deepseek":
        return create_deepseek_vision(
            model=spec.model,
            api_key=spec.api_key,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
            stream_usage=spec.stream_usage,
            timeout=spec.timeout,
            max_retries=spec.max_retries,
            enable_thinking=spec.enable_thinking,
            **spec.extra,
        )
    return create_qwen(
        model=spec.model,
        api_key=spec.api_key,
        base_url=spec.base_url,
        temperature=spec.temperature,
        enable_thinking=spec.enable_thinking,
        max_tokens=spec.max_tokens,
        stream_usage=spec.stream_usage,
        timeout=spec.timeout,
        max_retries=spec.max_retries,
        **spec.extra,
    )


# ===== qwen（langchain_qwq.ChatQwen，DashScope） =====


def create_qwen(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    enable_thinking: Optional[bool] = None,
    max_tokens: Optional[int] = None,
    stream_usage: bool = True,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    streaming: bool = False,
    **kwargs: Any,
) -> "ChatQwen":
    """
    工厂函数：创建 ChatQwen 实例（DashScope 官方集成）。

    默认值从 .env 配置读取（DASHSCOPE_MODEL / DASHSCOPE_API_KEY /
    DASHSCOPE_TEMPERATURE / DASHSCOPE_ENABLE_THINKING）。API 版 qwen 需显式
    ``enable_thinking=True`` 才开启思考（reasoning_content 由官方集成原生回传）。
    """
    if not _HAS_LANGCHAIN_QWQ:
        raise ImportError(
            "ChatQwen 需要 langchain-qwq：pip install langchain-qwq"
        )
    return ChatQwen(
        model=model or DEFAULT_MODEL,
        api_key=api_key if api_key is not None else _get_setting("DASHSCOPE_API_KEY"),
        base_url=base_url or DASHSCOPE_BASE_URL,
        temperature=temperature
        if temperature is not None
        else float(_get_setting("DASHSCOPE_TEMPERATURE", "1.2")),
        enable_thinking=enable_thinking
        if enable_thinking is not None
        else _get_setting("DASHSCOPE_ENABLE_THINKING", "true").lower() == "true",
        max_tokens=max_tokens,
        stream_usage=stream_usage,
        timeout=timeout,
        max_retries=max_retries,
        streaming=streaming,
        **kwargs,
    )


# ===== deepseek（ChatDeepSeekVision，官方端点） =====
#
# 背景：langchain-deepseek 官方集成文档标注 ChatDeepSeek 不支持图片输入（Image
# input ❌）。该声明来自包内 data/_profiles.py（models.dev 生成），其中未收录
# deepseek-v4-flash-vision-exp 条目。实测（见 orchestration/test_model.ipynb）：
# ChatDeepSeek 继承 BaseChatOpenAI，消息转换层对 image_url 内容块**原样透传**，
# DeepSeek 官方 API 的 vision-exp 可直接识图（invoke/stream/reasoning_content 均正常），
# 官方 ❌ 只是能力档案数据滞后，并非客户端拦截。
#
# 本子类的修正：补齐 vision-exp 的 ModelProfile（image_inputs=True），并预置
# 官方端点与 DEEPSEEK_API_KEY 默认值。生产环境未安装 langchain-deepseek 时
# 本段整体跳过（guarded import，不阻断 model_factory 其余导出）。

# vision-exp 能力档案（对齐 DeepSeek 官方文档 /guides/vision 与 /quick_start/pricing）
_DEEPSEEK_VISION_PROFILE: dict = {
    "name": "DeepSeek V4 Flash Vision Exp",
    "release_date": "2026-08-21",
    "text_inputs": True,
    "image_inputs": True,
    "image_url_inputs": True,
    "text_outputs": True,
    "reasoning_output": True,
    "tool_calling": True,
    "structured_output": True,
    "max_input_tokens": 1_000_000,
    "max_output_tokens": 384_000,
}

if _HAS_LANGCHAIN_DEEPSEEK:

    class ChatDeepSeekVision(_ChatDeepSeekBase):  # type: ignore[misc, valid-type]
        """DeepSeek 视觉模型封装（deepseek-v4-flash-vision-exp，官方 API 端点）。

        - 图片输入：标准 OpenAI 兼容 image_url 内容块（base64 data URL / 外部
          http(s) URL / Files API file_id），图片仅可出现在 user 消息中
        - 思考模式：DeepSeek 官方参数为 thinking: {"type": ...}（与 Qwen 的
          extra_body["enable_thinking"] 不同），默认开启，无需额外注入；
          reasoning_content 由父类 _create_chat_result / 流式 chunk 钩子提取
        - 注意走 DashScope 端点时不可用：DashScope 未托管 vision-exp（404），
          且其 deepseek 文本模型会静默丢弃图片
        """

        def _resolve_model_profile(self):
            if "vision" in (self.model_name or ""):
                return dict(_DEEPSEEK_VISION_PROFILE)
            return super()._resolve_model_profile()


def create_deepseek_vision(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stream_usage: bool = True,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    streaming: bool = False,
    enable_thinking: Optional[bool] = None,
    **kwargs: Any,
) -> "ChatDeepSeekVision":
    """
    工厂函数：创建 DeepSeek 视觉模型实例（官方 API 端点）。

    默认值从 .env 配置读取（DEEPSEEK_VISION_MODEL / DEEPSEEK_TEMPERATURE）。
    ``api_key`` 优先使用调用方传入（BYOK 用户 key），缺省回退环境 DEEPSEEK_API_KEY。
    ``enable_thinking`` 映射到 DeepSeek 官方参数 ``thinking: {"type": enabled/disabled}``
    （通过 extra_body 顶层透传）；None 时用 provider 默认（开启）。需要环境安装
    langchain-deepseek。
    """
    if not _HAS_LANGCHAIN_DEEPSEEK:
        raise ImportError(
            "ChatDeepSeekVision 需要 langchain-deepseek：pip install langchain-deepseek"
        )
    extra_body: dict[str, Any] = {}
    if enable_thinking is not None:
        extra_body["thinking"] = {
            "type": "enabled" if enable_thinking else "disabled"
        }
    return ChatDeepSeekVision(
        model=model or DEEPSEEK_VISION_MODEL_NAME,
        api_key=api_key if api_key is not None else _get_setting("DEEPSEEK_API_KEY"),
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature
        if temperature is not None
        else float(_get_setting("DEEPSEEK_TEMPERATURE", "0.7")),
        max_tokens=max_tokens,
        stream_usage=stream_usage,
        timeout=timeout,
        max_retries=max_retries,
        streaming=streaming,
        extra_body=extra_body or None,
        **kwargs,
    )


# ===== resolve_chat_model（按请求路由 + LRU + 负缓存） =====

_MODEL_CACHE_MAX = 32
# key: (provider, api_key_hash[, think_flag]) -> BaseChatModel（进程内 LRU）
_model_cache: "OrderedDict[tuple[str, ...], BaseChatModel]" = OrderedDict()
# 负缓存：曾 401/403 的 deepseek key hash 集合，命中即回退 qwen
_invalid_ds_keys: set[str] = set()


def _hash_key(key: Optional[str]) -> str:
    return hashlib.sha256((key or "").encode("utf-8")).hexdigest()[:16]


def _cache_get(key: tuple[str, ...]) -> Optional[BaseChatModel]:
    model = _model_cache.get(key)
    if model is None:
        return None
    _model_cache.move_to_end(key)
    return model


def _cache_put(key: tuple[str, ...], model: BaseChatModel) -> None:
    _model_cache[key] = model
    _model_cache.move_to_end(key)
    while len(_model_cache) > _MODEL_CACHE_MAX:
        _model_cache.popitem(last=False)


def mark_ds_key_invalid(api_key: str) -> None:
    """标记某 deepseek key 为无效（401/403），后续请求命中负缓存直接回退 qwen。"""
    _invalid_ds_keys.add(_hash_key(api_key))


def is_ds_key_invalid(api_key: str) -> bool:
    """判断某 deepseek key 是否已被标记无效（负缓存命中）。"""
    return _hash_key(api_key) in _invalid_ds_keys


def resolve_chat_model(
    *, user_ds_key: Optional[str] = None, enable_thinking: bool = True
) -> BaseChatModel:
    """按请求解析模型。

    - 有 user DS key：deepseek 视觉模型（LRU 缓存；若该 key 曾 401/403 命中负
      缓存则回退 qwen）
    - 无 key：qwen（DASHSCOPE_MODEL，默认 qwen3.8-flash）
    - ``enable_thinking`` 双端生效（D1 思考策略反转）：qwen 经 enable_thinking
      参数，deepseek 经 ``thinking: {"type": enabled/disabled}``（extra_body）；
      两侧缓存键均含思考维度（think/nothink 分开缓存）

    返回的模型一律 ``streaming=True``：本函数主要供 Agent 对话路径（SSE 流式
    逐 token 转发，见 chat.py _run_agent_sse）与记忆提取/摘要解析使用，
    streaming=True 保证流式事件与 usage_metadata（stream_usage）均正常。
    """
    if user_ds_key:
        key_hash = _hash_key(user_ds_key)
        if key_hash in _invalid_ds_keys:
            logger.warning(
                "[ModelFactory] deepseek key 已标记无效（负缓存），回退 qwen"
            )
            return resolve_chat_model(user_ds_key=None, enable_thinking=enable_thinking)
        # 缓存键含思考维度：同一 key 的 thinking/nothink 两个模型实例分开缓存
        cache_key = ("deepseek", key_hash, "think" if enable_thinking else "nothink")
        model = _cache_get(cache_key)
        if model is None:
            model = create_deepseek_vision(
                api_key=user_ds_key, streaming=True, enable_thinking=enable_thinking
            )
            _cache_put(cache_key, model)
        return model

    cache_key = ("qwen", "default" if enable_thinking else "nothink")
    model = _cache_get(cache_key)
    if model is None:
        model = create_qwen(enable_thinking=enable_thinking, streaming=True)
        _cache_put(cache_key, model)
    return model


# ===== token 工具（对齐 LangChain UsageMetadata 标准） =====


def extract_usage(message_or_usage: Any) -> dict:
    """从 AI 消息 / 流式 chunk / 原始 usage dict 提取 UsageMetadata 标准字段。

    返回 ``{input_tokens, output_tokens, total_tokens, cache_read_tokens,
    cache_write_tokens, reasoning_tokens}``；缺失字段为 0。兼容老式
    ``prompt_tokens / completion_tokens`` 字段回退。
    """
    usage = message_or_usage
    if not isinstance(usage, dict):
        usage = getattr(message_or_usage, "usage_metadata", None)
    if not usage:
        return {}
    try:
        usage = dict(usage)
    except Exception:
        return {}
    if not isinstance(usage, dict):
        return {}

    input_tokens = int(
        usage.get("input_tokens") or usage.get("prompt_tokens") or 0
    )
    output_tokens = int(
        usage.get("output_tokens") or usage.get("completion_tokens") or 0
    )
    result: dict = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(usage.get("total_tokens") or 0)
        or (input_tokens + output_tokens),
    }

    in_details = usage.get("input_token_details") or {}
    if isinstance(in_details, dict):
        result["cache_read_tokens"] = int(in_details.get("cache_read") or 0)
        result["cache_write_tokens"] = int(in_details.get("cache_write") or 0)
    else:
        result["cache_read_tokens"] = 0
        result["cache_write_tokens"] = 0

    out_details = usage.get("output_token_details") or {}
    if isinstance(out_details, dict):
        result["reasoning_tokens"] = int(out_details.get("reasoning") or 0)
    else:
        result["reasoning_tokens"] = 0

    return result


def estimate_tokens(text: str) -> int:
    """近似估算文本 token 数（LangChain 内置 ``count_tokens_approximately``）。

    替换 ``output_chars // 2`` 启发式；异常时兜底 ``len//2``。
    """
    try:
        return int(count_tokens_approximately([HumanMessage(content=str(text))]))
    except Exception:
        return max(1, len(str(text)) // 2)
