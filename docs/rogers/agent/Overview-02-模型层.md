# 模型层

## ChatDashScope 设计

模型层通过 `ChatDashScope` 类封装阿里云 DashScope 大模型，继承自 `ChatOpenAI`，以 OpenAI 兼容模式调用 DashScope API。

### 基础配置

- **API 端点**：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- **默认模型**：`qwen3.7-flash`（由 `DASHSCOPE_MODEL` 环境变量控制）
- **视觉模型备选**：`qwen3-vl-flash`（由 `DASHSCOPE_VISION_MODEL` 环境变量控制）
- **API 密钥**：由 `DASHSCOPE_API_KEY` 环境变量提供
- **温度参数**：默认 1.2（由 `DASHSCOPE_TEMPERATURE` 环境变量控制）
- **思考模式**：默认启用（由 `DASHSCOPE_ENABLE_THINKING` 环境变量控制）

### 思考内容提取

DashScope 模型在响应中返回 `reasoning_content` 字段（模型内部推理过程，类似"思考链"）。由于 LangChain 的 OpenAI 封装 >= 1.3 版本会丢弃未知字段，ChatDashScope 覆盖了消息构建逻辑来保留此字段：

- **非流式**：在父类完成标准结果创建后，从原始 API 响应的 `choices[].message.reasoning_content` 中重新提取，放入 `additional_kwargs["reasoning_content"]`
- **流式**：直接拦截原始的 DashScope SSE 事件流，从每个 chunk 的 `delta.reasoning_content` 中实时提取，逐帧构建 `ChatGenerationChunk`

### 流式实现

流式输出完全绕过父类的 chunk 转换逻辑，直接使用 OpenAI 客户端 API 创建原始流，然后手动将每个原始 chunk 转换为 LangChain 所需的 `ChatGenerationChunk`。这种直接拦截方式是在流式模式中可靠捕获 `reasoning_content` 的唯一手段。

转换过程：
1. 从原始 chunk 中提取 token 用量（`usage` 字段，仅在最后一个 chunk 出现）
2. 从 `delta` 中提取 reasoning_content，放入 `additional_kwargs`
3. 从 `delta.tool_calls` 中提取工具调用信息，转为 `ToolCallChunk`
4. 处理边界情况：仅含 usage 的空内容 chunk、仅含 role 的角色切换 chunk
5. 将所有情况以 `AIMessageChunk` 形式封入 `ChatGenerationChunk`

### Token 用量提取

从 DashScope 的原始 chunk 中提取 usage 时，同时支持两种字段名格式：

- OpenAI 格式：`prompt_tokens` / `completion_tokens` / `total_tokens`
- DashScope 原生格式：`input_tokens` / `output_tokens` / `total_tokens`

同时也支持 raw_usage 以 Pydantic 模型或普通 dict 两种形态传入，确保 DashScope 兼容模式下的兼容性。

### 多模态支持

消息转换使用 LangChain 内部的 `_convert_message_to_dict` 函数，该函数天然支持包含文本和图片的 content blocks 列表。用户消息中的图片 URL（支持 HTTP/HTTPS URL 和 base64 data URL）将被正确转换为 DashScope Qwen-VL 接口所需的格式。

### 工厂函数

`create_chat_dashscope()` 从环境变量读取配置，创建预配置的模型实例：
- 不发送 `stream_options` 参数（DashScope 兼容模式不支持此参数）
- 所有模型参数（model、temperature、enable_thinking）均有环境变量兜底

### 视觉模型

项目维护独立的视觉模型配置 `DASHSCOPE_VISION_MODEL`，默认 `qwen3-vl-flash`。当前工作流中，图片处理通过 chat 路由上传转换后统一发给主模型处理，视觉模型暂未作为独立 fallback 接入。
