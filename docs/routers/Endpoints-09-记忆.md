# 语义记忆接口

prefix: `/memory`

所有端点认证方式均为 get_current_user（Cookie JWT / Header JWT / API Key 多态）。

## 语义记忆列表（只读）

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/memory/semantic` |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| category | Optional[str] | 无 | preference / fact / rule / status |

**响应：`ResponseModel[list[SemanticMemoryOut]]`**

SemanticMemoryOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键（序列化为字符串） |
| subject | str | 三元组主语 |
| predicate | str | 三元组谓语 |
| object | str | 三元组宾语 |
| category | str | preference / fact / rule / status |
| confidence | float | 置信度（0-1） |
| version | int | 版本号 |
| updated_at | datetime | 更新时间 |
| source_episodic_id | Optional[UUID] | 来源情景记忆 ID（序列化为字符串） |

**逻辑：** 返回当前用户的语义记忆列表，仅 `status="active"` 记录，按 `updated_at` 倒序，最多 100 条。数据来源为 MemoryStore（独立 MemoryBase，非 app Base）。检索异常时返回 HTTP 500（`JSONResponse`，code=500），区别于常规 `ResponseModel` 的 HTTP 200 业务错误。

**调用方：** 前端聊天页「我的记忆」面板（useMemories hook，刷新时调用）。
