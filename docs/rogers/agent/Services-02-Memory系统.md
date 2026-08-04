# Memory 系统

## 架构概览

记忆系统是一个"认知智能"子系统，将对话中提取的用户信息结构化存储到三种记忆类型中，并在后续对话中作为上下文注入。

```
对话消息 → MemoryExtractor (LLM 提取)
             ↓
        MemoryPipeline (编排)
             ↓
    ┌────────┼────────┐
    ↓        ↓        ↓
 Episodic  Semantic  Procedural
 (经历)    (知识)    (技能)
    ↓        ↓        ↓
        MemoryStore (pgvector)
             ↓
        MemoryPipeline.get_memory_context()
             ↓
        注入 System Prompt
```

## 三种记忆类型

### Episodic Memory（情景记忆）

记录用户的**经历和事件**。数据库表 `episodic_memories`：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| user_id | String(100) | 用户标识，索引 |
| content | Text | 原始内容 |
| summary | Text | AI 生成的摘要 |
| embedding | Vector(1024) | 语义搜索用向量 |
| memory_type | String(50) | conversation / event / observation |
| timestamp | DateTime | 事件发生时间 |
| importance_score | Float(0-1) | 重要性评分 |
| emotional_valence | String(20) | positive / negative / neutral |
| access_count | Integer | 遗忘曲线计数值 |
| last_accessed | DateTime | 最后访问时间 |
| decay_factor | Float | 遗忘倍率 |
| source_thread_id | String(100) | 来源对话 |
| source_message_ids | ARRAY(String) | 来源消息 ID |

索引：`(user_id, timestamp)`、`(user_id, memory_type)`、`(importance_score)`

### Semantic Memory（语义记忆）

存储关于用户的**事实和知识**，以 SPO 三元组形式（subject-predicate-object）。数据库表 `semantic_memories`：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| user_id | String(100) | 索引 |
| subject | String(200) | 三元组主语 |
| predicate | String(200) | 三元组谓语 |
| object | Text | 三元组宾语 |
| category | String(50) | preference / fact / rule / status |
| confidence | Float(0-1) | 置信度 |
| source_episodic_id | UUID FK | 来源情景记忆 |
| version | Integer | 版本号 |
| status | String(20) | active / superseded |
| superseded_by | UUID FK | 版本链 |

索引：`(user_id, category)`、`(user_id, status)`、`(user_id, subject, predicate)`

版本管理：当相同的 `(subject, predicate)` 有新的存储请求时，旧记录被标记为 `superseded`，版本号递增，形成事实版本链。

### Procedural Memory（程序记忆）

存储**可执行的技能和流程**。数据库表 `procedural_memories`：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID PK | 主键 |
| user_id | String(100) | 索引 |
| name | String(200) | 技能名称 |
| description | Text | 描述 |
| steps | JSONB | 步骤数组 `[{step, action, params}]` |
| embedding | Vector(1024) | 语义搜索向量 |
| success_count | Integer | 成功计数 |
| failure_count | Integer | 失败计数 |
| last_used | DateTime | 最后使用时间 |
| trigger_conditions | JSONB | 触发条件 `{keywords, context}` |

## 嵌入模型

使用阿里云 DashScope 的 `text-embedding-v3` 模型，通过 LlamaIndex 的 `DashScopeEmbedding` 接入。向量维度 1024（可通过环境变量配置）。存储使用 PostgreSQL pgvector 扩展。嵌入模型实例为全局单例，使用 `@lru_cache` 缓存。

## 记忆提取器 (MemoryExtractor)

使用 LLM（调用独立模型实例）从对话文本中提取结构化记忆，返回三种记忆类型。

提取流程：
1. 将对话消息格式化为 `role: content` 行
2. 跳过字符数 < 50 的短对话
3. 调用 LLM 提取
4. 解析结构化 JSON 响应（兼容 Markdown 代码块包裹）
5. 过滤低重要性（`min_importance` = 0.3）

每个提取结果包含：
- Episodic: content、memory_type、importance、emotional_valence、summary
- Semantic: subject、predicate、object、category、confidence
- Procedural: name、steps、description、trigger_conditions

## 记忆存储 (MemoryStore)

基于 SQLAlchemy + pgvector 的存储层。

### 核心操作

| 操作 | 方法 | 说明 |
|------|------|------|
| 存储情景记忆 | store_episodic() | 生成 embedding，存储含元数据 |
| 检索情景记忆 | retrieve_episodic() | 混合检索：SQL 过滤 + 余弦相似度排序 |
| 检索近期情景 | get_recent_episodic() | 基于时间（最近 N 天） |
| 存储语义记忆 | store_semantic() | 自动版本管理 |
| 检索语义记忆 | retrieve_semantic() | 仅返回 status="active" |
| 搜索语义记忆 | search_semantic() | embedding 相似度搜索 |
| 存储程序记忆 | store_procedural() | 从 name+description 生成 embedding |
| 检索程序记忆 | retrieve_procedural() | embedding 相似度 + 使用统计 |
| 记录程序使用 | record_procedural_usage() | 更新成功/失败计数 |

### 遗忘曲线

基于艾宾浩斯遗忘曲线的衰减实现：
- 记忆创建时间
- 最后访问时间和频率
- 初始重要性评分（高重要性的记忆衰减更慢）
- 衰减率参数（默认每 30 天一个衰减周期）

公式：`新衰减 = max(最小衰减, 原衰减因子 × (1 - 衰减率 × 经过天数/30))`

### 容量上限与淘汰策略

情景记忆与程序记忆无去重机制，为控制存储增长，每用户设置上限条数（可通过环境变量配置，0 表示不限制）：

| 记忆类型 | 配置项 | 默认上限 | 淘汰策略 |
|----------|--------|----------|----------|
| 情景记忆 | `MEMORY_EPISODIC_MAX` | 200 | 超出后按 重要性升序 → 时间升序 删除（低重要性且最旧的先删） |
| 程序记忆 | `MEMORY_PROCEDURAL_MAX` | 50 | 超出后按 最久未使用 → 创建时间升序 删除 |

淘汰在写入时触发（`store_episodic` / `store_procedural` 提交后执行 `_trim_memories`）。删除情景记忆前会先清空语义记忆中对应的 `source_episodic_id` 引用（无 ON DELETE 约束，避免外键冲突）。语义记忆走版本管理不设上限。

## 记忆管道 (MemoryPipeline)

编排完整的记忆生命周期：

| 操作 | 方法 | 说明 |
|------|------|------|
| 处理对话 | process_conversation() | 提取并分类存储 |
| 整理记忆 | consolidate_memories() | 合并重复（同 subject/predicate 保留 version 最大，其余标 superseded）+ LLM 升华（从已有记忆提炼更高层洞察，去重后存入）+ 记录 memory_consolidation_logs |
| 应用遗忘 | apply_forgetting_curve() | 定期衰减 |
| 生成上下文 | get_memory_context() | 格式化注入 System Prompt |

`get_memory_context()` 的输出示例：
```
# 记忆上下文
## 相关经历
- [2026-07-28] 用户完成了5公里跑步...
## 用户信息
- 用户 偏好 运动时间: 晨跑
## 可用技能
- 哑铃训练: 如何使用哑铃进行...
```

## 语义记忆只读接口

语义记忆支持只读查询接口，供前端「我的记忆」面板使用：

| 项目 | 值 |
|------|-----|
| 端点 | GET `/api/memory/semantic` |
| 认证 | get_current_user（Cookie JWT / Header JWT / API Key 多态） |
| 参数 | category 可选（preference/fact/rule/status） |
| 逻辑 | 仅返回 status="active" 记录，按 updated_at 倒序，最多 100 条 |
| 数据源 | MemoryStore（独立 MemoryBase，非 app Base） |
| 异常 | 检索失败返回 HTTP 500（JSONResponse，code=500） |

接口契约详见 `docs/routers/Endpoints-09-记忆.md`。记忆提取由 `MemoryUpdateMiddleware` 在累计 token 达到阈值（100,000）时触发（详见 Overview-03-中间件管道.md）。
