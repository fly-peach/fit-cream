# 服务层

## 三层架构

前端 API 调用分为三层：通用请求层（api.ts）、领域封装层（kb-api.ts）、流式传输层（sse-client.ts）。

---

## API 客户端（lib/api.ts）

通用 HTTP 客户端，基于原生 fetch 封装。

### 配置

| 参数 | 值 |
|------|-----|
| 基础 URL | `/api`（同源相对路径，开发环境通过 Vite proxy 转发） |
| 认证注入 | 请求时读取 `useAuthStore.getState().token`，设为 `Authorization: Bearer <token>` |
| 响应解析 | `{ code, message, data }` 信封，code 为 0/200 视为成功 |

### 错误处理

| 场景 | 行为 |
|------|------|
| HTTP 非 200 | 抛 ApiError |
| code 在 40100-40199 范围 | 执行 `useAuthStore.logout()`（登出原因："登录已过期，请重新登录"） |
| 其他非 0 code | 抛 ApiError（携带 code + message） |

### 导出方法

| 方法签名 | 功能 |
|----------|------|
| api.get(path, params?) | GET 请求，params 自动转为 query string |
| api.post(path, body?) | POST 请求 |
| api.put(path, body?) | PUT 请求 |
| api.patch(path, body?) | PATCH 请求 |
| api.delete(path) | DELETE 请求 |
| api.upload(path, formData) | multipart/form-data 上传（不设置 Content-Type，由浏览器自动处理 boundary） |

### 辅助函数

| 函数 | 用途 |
|------|------|
| ApiError | 自定义错误类（code + message + data） |
| isAuthError(code) | 判断 code 是否在 401xx 范围 |
| checkAuthEnvelope(json) | 为直接 fetch 调用者检测认证错误信封 |

---

## 知识库 API（lib/kb-api.ts）

领域封装层，基于 `api` 对象，覆盖 27 个方法。

### 类型

KBListItem、KB、KBDocument、KBDocumentContent、KBSearchResult、KBGraphNode、KBGraphEdge、KBGraphData、KBSubscription、KBToken、KBTokenCreated、KBCreateInput、KBUpdateInput、KBVisibilityInput、KBDocumentCreateInput、KBDocumentContentUpdateInput、KBDocumentMetaUpdateInput、KBTokenCreateInput

### 端点映射

**用户操作（只读 + 订阅）：**

| 方法 | 路径 |
|------|------|
| kbApi.list() | GET /knowledge-bases |
| kbApi.mySubscriptions() | GET /knowledge-bases/subscriptions |
| kbApi.get(id) | GET /knowledge-bases/:id |
| kbApi.subscribe(id) | POST /knowledge-bases/:id/subscribe |
| kbApi.unsubscribe(id) | DELETE /knowledge-bases/:id/subscribe |
| kbApi.listDocuments(id, params) | GET /knowledge-bases/:id/documents |
| kbApi.getDocument(kbId, docId) | GET /knowledge-bases/:id/documents/:docId |
| kbApi.readDocument(kbId, docId) | GET /knowledge-bases/:id/documents/:docId/content |
| kbApi.search(kbId, query, limit) | GET /knowledge-bases/:id/search |
| kbApi.getGraph(kbId) | GET /knowledge-bases/:id/graph |
| kbApi.getReferences(kbId, docId) | GET /knowledge-bases/:id/documents/:docId/references |

**管理员操作（写）：**

| 方法 | 路径 |
|------|------|
| kbApi.create(data) | POST /knowledge-bases |
| kbApi.update(id, data) | PUT /knowledge-bases/:id |
| kbApi.remove(id) | DELETE /knowledge-bases/:id |
| kbApi.setVisibility(id, data) | POST /knowledge-bases/:id/share |
| kbApi.createDocument(kbId, data) | POST /knowledge-bases/:id/documents |
| kbApi.uploadDocument(kbId, formData) | POST /knowledge-bases/:id/documents/upload |
| kbApi.updateDocContent(kbId, docId, data) | PUT /knowledge-bases/:id/documents/:docId/content |
| kbApi.updateDocMeta(kbId, docId, data) | PATCH /knowledge-bases/:id/documents/:docId |
| kbApi.deleteDocument(kbId, docId) | DELETE /knowledge-bases/:id/documents/:docId |
| kbApi.reindex(kbId) | POST /knowledge-bases/:id/reindex |
| kbApi.rebuildGraph(kbId) | POST /knowledge-bases/:id/rebuild-graph |
| kbApi.lint(kbId) | GET /knowledge-bases/:id/lint |
| kbApi.listSubscribers(kbId) | GET /knowledge-bases/:id/subscribers |
| kbApi.removeSubscriber(kbId, userId) | DELETE /knowledge-bases/:id/subscribers/:userId |
| kbApi.createToken(kbId, data) | POST /knowledge-bases/:id/tokens |
| kbApi.listTokens(kbId) | GET /knowledge-bases/:id/tokens |
| kbApi.revokeToken(kbId, tokenId) | DELETE /knowledge-bases/:id/tokens/:tokenId |

---

## SSE 流式客户端（lib/sse-client.ts）

用于聊天 SSE 流式对话。

### streamChat

| 参数 | 类型 | 说明 |
|------|------|------|
| message | str | 消息文本 |
| threadId | str \| null | 线程标识 |
| signal? | AbortSignal | 用于中断请求 |
| token? | str | JWT Token（优先于 store） |
| images? | str[] | 图片 base64 data URL |

**返回：** `AsyncGenerator<SSEEvent>` — 按行解析 SSE 协议 `event:\ndata:\n\n`

**非流式兜底：** 当响应 `content-type` 非 `text/event-stream` 时，按 JSON 信封解析，检测 `401xx` 触发登出。

### stopGeneration

| 参数 | 说明 |
|------|------|
| threadId | 要停止的线程 ID |
| token? | JWT Token |

调用 `POST /api/chat/stop`，最佳尝试（错误忽略除认证外）。

---

## Hooks

### useChatSSE（use-chat-sse.ts）

驱动聊天页面的核心 Hook。

| 返回 | 类型 | 说明 |
|------|------|------|
| messages | ChatMessage[] | 消息列表 |
| sendMessage(content, images?) | () => void | 发送消息 |
| stop() | () => void | 中断流式输出 |
| clearMessages() | () => void | 清空消息 |
| isStreaming | boolean | 流式传输中 |
| thinking | string | 当前推理内容 |
| usage | TokenUsage \| null | Token 用量 |
| setMessages | (msgs) => void | 手动设置消息 |
| setUsage | (usage) => void | 手动设置用量 |

**执行流程：**
1. sendMessage 创建用户消息 + 助手占位消息
2. `for await (const event of streamChat(...))` 循环处理事件
3. 事件分发：
   - `start` → 同步 thread_id 到 useChatStore
   - `thinking` → 累积推理内容，记录 thinkingOffset
   - `step` → 追加 AgentStep（thought 增量累积 / tool 新建步骤 / tool_result 匹配更新）
   - `token` → 追加助手回复文本
   - `tool_start` → 添加 ToolCall（run_id 为 id，记录 thinkingOffset）
   - `tool_result` → 按 id 匹配 → 更新为 completed
   - `usage` → 累积 TokenUsage
   - `done`/`stopped`/`error` → 结束流式处理
4. stop() → AbortController.abort() + POST /chat/stop

**依赖：** sse-client、nanoid、useChatStore、types/chat

### useThreads（use-threads.ts）

线程管理 Hook。

| 返回 | 类型 | 说明 |
|------|------|------|
| threads | Thread[] | 线程列表 |
| isLoading | boolean | 加载中 |
| loadThreads() | () => void | 刷新列表 |
| deleteThread(id) | () => void | 删除线程 |
| clearHistory() | () => void | 清空所有历史 |
| renameThread(id, title) | Promise<boolean> | 改名（乐观更新，失败回滚） |

**类型 Thread：** id, title, lastMessage, createdAt, updatedAt, messageCount, totalTokens

**API 调用：** `GET /api/chat/threads`、`DELETE /api/chat/threads/{id}`、`DELETE /api/chat/history`、`PATCH /api/chat/threads/{id}/title`

### useMemories（use-memories.ts）

「我的记忆」面板数据 Hook（语义记忆只读查询）。

| 返回 | 类型 | 说明 |
|------|------|------|
| data | SemanticMemoryItem[] | 语义记忆列表 |
| loading | boolean | 加载中 |
| error | string \| null | 加载错误（认证失败由 api 层自动登出） |
| refetch | () => void | 重新拉取 |

**类型 SemanticMemoryItem：** id, subject, predicate, object, category(preference/fact/rule/status), confidence, version, updated_at, source_episodic_id

**API 调用：** `GET /api/memory/semantic`（挂载时自动拉取）
