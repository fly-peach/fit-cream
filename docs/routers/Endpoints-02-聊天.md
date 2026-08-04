# 聊天接口

prefix: `/chat`

所有端点认证方式均为 JWT（get_current_user）。

## 发送消息（流式）

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/chat/message` |

**请求体：ChatRequest**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| message | Optional[str] | 最多 4000 字符 | 文本消息 |
| images | Optional[list[str]] | 最多 10 条 | 图片 URL 或 base64 data URL |
| thread_id | Optional[str] | 最多 100 字符 | 线程标识（UUID 或已有 ID） |

校验：message 和 images 至少提供一个，不可同时为空。

**响应：`StreamingResponse`（SSE，`text/event-stream`）**

### SSE 事件类型

| 事件名 | 触发时机 | data 字段 |
|--------|----------|-----------|
| start | 流开始 | `{"thread_id": str}` |
| thinking | 模型推理中 | `{"content": str}`（reasoning_content 逐块） |
| token | 文本生成中 | `{"content": str}`（回复文本逐块） |
| step | ReAct 步骤流（与 thinking/tool_* 并行） | `{"type": str, ...}`，type 为 `thought`（含 `delta` 推理增量）/ `tool`（含 `id/tool/input` 工具开始）/ `tool_result`（含 `id/tool/data` 工具结果，data 截断 2000 字符） |
| tool_start | 工具调用开始 | `{"id": str, "tool": str, "input": dict}` |
| tool_result | 工具调用完成 | `{"id": str, "tool": str, "data": str}`（输出截断 2000 字符） |
| usage | 流结束前 | `{"input_tokens": int, "output_tokens": int, "total_tokens": int}` |
| done | 成功结束 | `{"thread_id": str, "tool_calls": list}` |
| stopped | 用户中断 | `{"thread_id": str, "partial_content": str}` |
| error | 异常 | `{"message": str}` |

**执行流程：**
1. 构建用户动态上下文（当前日期 + 用户称呼，身体数据/打卡/计划改为按需工具获取）
2. Agent 发送前清理 checkpoint 中已过期的多模态图片签名 URL（替换为占位文本，避免无效图片重复发送）
3. 保存用户消息到 DB（conversations 表，图片 URL 列表记录到 metadata_json.images 供历史渲染）
4. 调用 LangGraph Agent 的 `astream_events` 流式输出
5. 按 SSE 事件类型逐帧转发（thinking/token/step/tool_start/tool_result）
6. 流结束时保存助手消息（metadata 含 thinking/tool_calls/steps），累加 Token 用量到 thread_usages

## 停止生成

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/chat/stop` |

**请求体：StopRequest**

| 字段 | 类型 |
|------|------|
| thread_id | str |

逻辑：设置 `asyncio.Event` 通知对应活跃流停止。无活跃流时返回 404。

## 上传图片

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/chat/upload-image` |

**请求体：** multipart file

| 字段 | 类型 | 约束 |
|------|------|------|
| file | UploadFile | jpg/png/webp/gif，最大 10MB |

**响应：`ResponseModel[dict]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| url | str | OSS 签名 URL（有效期由 `OSS_SIGN_URL_EXPIRES` 控制，默认 15 天）；OSS 未配置或上传失败时回退为 base64 data URL |
| filename | str | 文件名 |
| size | int | 文件大小 |
| mime_type | str | MIME 类型 |

逻辑：图片涉及用户隐私，上传至 OSS 私有路径 `chat/{user_id}/{uuid}.{ext}`，ACL 设为私有，返回签名 URL（`OSS_SIGN_URL_EXPIRES` 控制，默认 1296000 秒 = 15 天，兼顾跨天对话图片可见与泄露风险）。该 URL 可直接嵌入前端或传给 DashScope 多模态接口。OSS 未配置（缺 AccessKey 等）或上传异常时回退 base64 data URL（开发模式）。

过期清理：每次 Agent 发送前解析历史多模态消息中的签名 URL 的 `Expires` 参数，已过期图片替换为占位文本 `[图片已分析完毕]`，避免每轮重复发送无效图片浪费 token（`chat.py::_clean_expired_image_urls`）。

## 线程列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/chat/threads` |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 20 | 1-100 |

**响应：`ResponseModel[list[ThreadOut]]`**

ThreadOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| thread_id | str | 线程标识 |
| title | Optional[str] | 自定义标题 |
| last_message | Optional[str] | 最后一条消息（截断 100 字符） |
| message_count | int | 消息数 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| total_tokens | int | 累计 Token 用量 |

## 线程消息

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/chat/threads/{thread_id}/messages` |

**路径参数：** thread_id

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | ge 1 |
| size | int | 50 | 1-200 |

**响应：`ResponseModel[ThreadMessagesOut]`**

ThreadMessagesOut：

| 字段 | 类型 |
|------|------|
| thread_id | str |
| messages | list[MessageOut] |
| total | int |

MessageOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| role | str | user / assistant / tool |
| content | Optional[str] | 消息内容 |
| metadata_json | Optional[dict] | 元数据（thinking、tool_calls、steps、stopped、images） |
| created_at | datetime | 创建时间 |

说明：`metadata_json.images` 记录用户消息附带的历史图片 URL（前端历史消息按原图渲染）；`metadata_json.steps` 记录助手消息的 ReAct 步骤序列（前端 AgentTrace 组件平铺渲染）。

## 更新线程标题

| 项目 | 值 |
|------|-----|
| 方法 | PATCH |
| 路径 | `/api/chat/threads/{thread_id}/title` |

**路径参数：** thread_id

**请求体：ThreadTitleIn**

| 字段 | 类型 | 约束 |
|------|------|------|
| title | str | 1-200 字符 |

逻辑：Upsert ThreadMeta，通过消息存在性校验线程所有权。

**响应：`ResponseModel[ThreadOut]`**

## 删除线程

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/chat/threads/{thread_id}` |

逻辑：删除所有 Conversation 记录 + ThreadMeta。通过用户作用域隔离。

## 清空历史

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/chat/history` |

逻辑：删除当前用户所有对话消息和线程元数据。
