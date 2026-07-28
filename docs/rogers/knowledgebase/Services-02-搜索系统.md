# 搜索系统

知识库搜索不依赖外部向量数据库或嵌入模型，而是使用 **PostgreSQL 内置全文搜索**。

## 全文搜索架构

### 搜索向量生成

`kb_chunks` 表包含一个 `Generated Column`：

```
search_vector = to_tsvector('simple', content)
```

- 使用 PostgreSQL 的 `simple` 词典（不进行词干还原，中文按字匹配）
- 列定义为 `PERSISTED`，内容更新时数据库自动维护
- GIN 索引加速 `@@` 搜索操作符

### 查询语法

使用 `websearch_to_tsquery('simple', query)` 解析用户查询，支持 Google 风格语法：

- 普通词：OR 组合
- `"引号"`：精确短语
- `-排除词`：排除
- `OR`：显式 OR

### 排序

结果排序使用 `ts_rank(search_vector, tsquery)` 相关性评分：
- 基于 BM25 算法变体
- 考虑词频、文档长度、逆文档频率
- 结果按评分降序排列

## 搜索流程

1. 用户输入搜索查询
2. 验证查询非空
3. 通过 `websearch_to_tsquery` 解析查询
4. 在 `kb_chunks` 表上执行 `@@` 搜索操作符
5. 通过 `JOIN kb_documents` 过滤非 archived 文档
6. 按 `ts_rank` 降序排序
7. 限制返回数量（默认 20）
8. 返回结果含：块内容、文档标题、面包屑、评分

## Agent 集成搜索

Agent 工具 `search_knowledge_base` 的搜索范围：

1. 如果指定了 `kb_id`：
   - 检查用户是否订阅了该知识库
   - 仅在该知识库内搜索
2. 如果未指定 `kb_id`：
   - 查询用户的订阅列表
   - 在所有已订阅的知识库中并行搜索
   - 合并结果，统一按评分排序

每个搜索结果的元数据包含：
- chunk_id、document_id、kb_id
- 块内容（截断）
- 标题
- 标层面包屑
- 相关性评分
- 块序号、总块数

## 局限性

当前搜索系统的已知局限：
- 不支持语义搜索（依赖关键词匹配而非向量相似度）
- 无重排序机制（仅依赖 `ts_rank`）
- 无查询扩展或同义词处理
- 中英文混合查询可能不够精准（`simple` 词典不做中文分词）

记忆系统的向量搜索是独立的 pgvector 实现，与知识库的全文搜索互不关联。
