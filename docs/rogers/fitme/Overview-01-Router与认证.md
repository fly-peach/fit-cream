# Router 与认证

> 认证系统（注册/登录/JWT/Token 管理）详见 `docs/rogers/auth/`
> 接口端点详细契约（请求体/响应体/参数/认证方式/业务逻辑）详见 `docs/routers/`

## API 路由总览

所有路由统一挂载在 `/api` 前缀下。JWT 认证通过 `get_current_user` 依赖从 `Authorization: Bearer <token>` 解析用户。

### 认证

| 端点 | 路径 | 方法 | 认证 | 用途 |
|------|------|------|------|------|
| 注册 | /api/auth/register | POST | 无 | 注册新用户 |
| 登录 | /api/auth/login | POST | 无 | 登录 |
| 刷新令牌 | /api/auth/refresh | POST | 无 | 刷新令牌 |
| 获取个人信息 | /api/users/me | GET | JWT | 当前用户完整资料 |
| 更新个人信息 | /api/users/me | PUT | JWT | 部分更新用户资料 |

### 聊天

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 发送消息 | /api/chat/message | POST | SSE 流式对话（核心入口） |
| 停止生成 | /api/chat/stop | POST | 中断当前流式输出 |
| 上传图片 | /api/chat/upload-image | POST | 图片 → base64 data URL |
| 线程列表 | /api/chat/threads | GET | 用户所有对话线程（分页） |
| 线程消息 | /api/chat/threads/{id}/messages | GET | 指定线程的消息列表（分页） |
| 更新标题 | /api/chat/threads/{id}/title | PATCH | 设置自定义线程标题 |
| 删除线程 | /api/chat/threads/{id} | DELETE | 删除线程所有消息 |
| 清空历史 | /api/chat/history | DELETE | 清空用户所有对话 |

聊天路由核心流程：
1. 前端发送 `ChatRequest{message, images?, thread_id?}`
2. 后端构建用户动态上下文（身体数据、BMI、打卡天数、活跃计划）
3. 调用 LangGraph Agent 的 `astream_events` 流式输出
4. 按 SSE 事件类型逐帧转发给前端
5. 流结束时保存消息并累加 Token 用量

### 训练计划

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 列表 | /api/plans | GET | 分页，支持 status 过滤 |
| 活跃计划 | /api/plans/active | GET | 当前活跃计划 |
| 详情 | /api/plans/{id} | GET | 含 days + exercises |
| 创建 | /api/plans | POST | 含 days/exercises |
| 更新 | /api/plans/{id} | PUT | 部分更新 |
| 删除 | /api/plans/{id} | DELETE | 物理 CASCADE 删除 |
| 添加日 | /api/plans/{id}/days | POST | |
| 更新日 | /api/plans/days/{id} | PUT | |
| 删除日 | /api/plans/days/{id} | DELETE | |
| 添加动作 | /api/plans/days/{id}/exercises | POST | |
| 更新动作 | /api/plans/exercises/{id} | PUT | |
| 删除动作 | /api/plans/exercises/{id} | DELETE | |

### 饮食计划

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 列表 | /api/diet-plans | GET | 分页 |
| 活跃 | /api/diet-plans/active | GET | |
| 详情 | /api/diet-plans/{id} | GET | |
| 创建 | /api/diet-plans | POST | |
| 更新 | /api/diet-plans/{id} | PUT | |
| 删除 | /api/diet-plans/{id} | DELETE | 软删除（archive） |
| 添加日 | /api/diet-plans/{id}/days | POST | |
| 更新日 | /api/diet-plans/days/{id} | PUT | |
| 更新餐 | /api/diet-plans/meals/{id} | PUT | |
| 删除餐 | /api/diet-plans/meals/{id} | DELETE | |

### 打卡

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 列表 | /api/checkins | GET | 分页，日期范围过滤 |
| 连续天数 | /api/checkins/streak | GET | 当前/最长连续 |
| 详情 | /api/checkins/{id} | GET | |
| 创建 | /api/checkins | POST | 每人每天一次 |
| 更新 | /api/checkins/{id} | PUT | |

### 动作库

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 搜索 | /api/exercises | GET | 多维度过滤 |
| 详情 | /api/exercises/{id} | GET | |

### 统计

| 端点 | 路径 | 方法 | 用途 |
|------|------|------|------|
| 周统计 | /api/stats/weekly | GET | |
| 月统计 | /api/stats/monthly | GET | |
| 身体数据 | /api/stats/body | GET | |
| 总览 | /api/stats/overview | GET | 含累计数据 + 连续打卡 |


## 响应格式

所有 API 使用统一的 `ResponseModel<T>` 包装：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页响应使用 `PaginatedResponse<T>`：

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "size": 20,
  "total_pages": 5,
  "has_next": true
}
```
