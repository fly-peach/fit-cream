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
| tool_start | 工具调用开始 | `{"id": str, "tool": str, "input": dict}` |
| tool_result | 工具调用完成 | `{"id": str, "tool": str, "data": str}`（输出截断 2000 字符） |
| usage | 流结束前 | `{"input_tokens": int, "output_tokens": int, "total_tokens": int}` |
| done | 成功结束 | `{"thread_id": str, "tool_calls": list}` |
| stopped | 用户中断 | `{"thread_id": str, "partial_content": str}` |
| error | 异常 | `{"message": str}` |

**执行流程：**
1. 构建用户动态上下文（日期、目标、BMI、打卡连续天数、活跃计划）
2. 保存用户消息到 DB（conversations 表）
3. 调用 LangGraph Agent 的 `astream_events` 流式输出
4. 按 SSE 事件类型逐帧转发
5. 流结束时保存助手消息并累加 Token 用量到 thread_usages

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
| url | str | data:base64 URL |
| filename | str | 文件名 |
| size | int | 文件大小 |
| mime_type | str | MIME 类型 |

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
| metadata_json | Optional[dict] | 元数据（thinking、tool_calls、stopped、images） |
| created_at | datetime | 创建时间 |

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
