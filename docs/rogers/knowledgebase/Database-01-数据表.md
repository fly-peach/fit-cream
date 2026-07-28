# 知识库数据库设计

知识库系统使用 PostgreSQL 存储，共 6 张表。

## 核心表

### knowledge_bases — 知识库表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | |
| name | VARCHAR(200) | | 知识库名称 |
| description | TEXT | | 描述 |
| slug | VARCHAR(100) | UNIQUE, 索引 | URL 友好标识 |
| owner_id | UUID | FK→users.id, 索引 | 所有者 |
| visibility | VARCHAR(20) | | private / shared / public |
| share_token | VARCHAR(64) | UNIQUE, 预生成 | 分享链接 token |
| public_slug | VARCHAR(80) | nullable, 部分唯一 | 公开访问路径 |
| schema_config | JSONB | | 实体类型模板配置 |
| created_at | DateTime(tz) | server_default=now() | |
| updated_at | DateTime(tz) | server_default=now(), onupdate=now() | |

约束：当 visibility 为 public 时，public_slug 必须非空。

### kb_documents — 文档表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| kb_id | UUID | FK→knowledge_bases.id CASCADE, 索引 | 所属知识库 |
| title | VARCHAR(500) | | 文档标题 |
| filename | VARCHAR(255) | | 原始文件名 |
| path | VARCHAR(500) | | 路径（/wiki/* 或 /） |
| source_kind | VARCHAR(20) | | raw / wiki |
| file_type | VARCHAR(20) | | md、pdf 等 |
| content | TEXT | | 完整 Markdown 文本 |
| content_hash | VARCHAR(64) | SHA256 | 内容哈希（增量索引用） |
| status | VARCHAR(20) | | pending / processing / ready / failed / archived |
| document_number | Integer | | 每个知识库内自增编号 |
| sort_order | Integer | | 排序 |
| archived | Boolean | | 软删除标记 |
| parser | VARCHAR(50) | | 解析器类型（unstructured） |
| page_count | Integer | | PDF 页数（≤300） |
| last_indexed_at | DateTime(tz) | | 最后索引时间 |
| stale_since | DateTime(tz) | | 引用源更新导致的陈旧标记 |
| tags | JSONB | | 标签 |
| entity_type | VARCHAR(50) | 索引 | 实体类型（如 exercise） |
| metadata_ | JSONB | | 自定义元数据 |
| version | Integer | | 乐观锁版本号 |
| created_by | UUID | FK→users.id | 创建者 |
| created_at / updated_at | DateTime(tz) | server_default=now() | |

### kb_chunks — 文档分块表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| document_id | UUID | FK→kb_documents.id CASCADE, 索引 | 所属文档 |
| chunk_index | Integer | | 块序号（文档内递增） |
| content | TEXT | max 10,000 chars | 块内容 |
| source_content | TEXT | nullable | 来源原始内容 |
| token_count | Integer | | CJK 感知的 token 估算 |
| start_char | Integer | | 在原始文档中的起始位置 |
| header_breadcrumb | VARCHAR(500) | | 标层面包屑（如 "训练 > 胸部 > 卧推"） |
| search_vector | TSVECTOR | GENERATED ALWAYS 持久化 | PostgreSQL 全文搜索向量 |

索引：GIN 索引在 `search_vector` 上。
唯一约束：`(document_id, chunk_index)`

### kb_references — 知识图谱边表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| source_document_id | UUID | FK→kb_documents.id CASCADE | 源文档 |
| target_document_id | UUID | FK→kb_documents.id CASCADE | 目标文档 |
| kb_id | UUID | FK→knowledge_bases.id CASCADE, 索引 | 所属知识库 |
| reference_type | VARCHAR(20) | | cites / links_to |
| page | Integer | nullable | 引用页码 |

唯一约束：`(source_document_id, target_document_id, reference_type)`

### kb_subscriptions — 用户订阅表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| kb_id | UUID | FK→knowledge_bases.id CASCADE | |
| user_id | UUID | FK→users.id CASCADE | |
| subscribed_at | DateTime(tz) | | 订阅时间 |

唯一约束：`(kb_id, user_id)`

### kb_api_tokens — API Token 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | |
| kb_id | UUID | FK→knowledge_bases.id CASCADE | |
| token_hash | VARCHAR(255) | UNIQUE | SHA256 哈希 |
| token_prefix | VARCHAR(16) | | 前 12 字符用于显示 |
| name | VARCHAR(100) | | Token 名称 |
| scope | VARCHAR(20) | | read / write |
| created_by | UUID | FK→users.id | 创建者 |
| last_used_at | DateTime(tz) | | 最后使用时间 |
| expires_at | DateTime(tz) | nullable | 过期时间 |
| revoked_at | DateTime(tz) | nullable | 撤销时间（软撤销） |

## 核心设计

### 全文搜索

知识库的搜索不使用向量嵌入，而是依赖 PostgreSQL 内置的全文搜索：

- `kb_chunks.search_vector` 是 **Generated Column**（`to_tsvector('simple', content)`），由 PostgreSQL 自动维护
- GIN 索引加速 `@@` 搜索操作符
- 查询通过 `websearch_to_tsquery` 解析（支持 Google 风格搜索语法）
- 排序使用 `ts_rank` 相关性评分

### 内容哈希增量索引

`kb_documents.content_hash`（SHA256）用于增量索引：仅当内容哈希变化或从未索引过的文档需要重新分块。

### 乐观锁

`kb_documents.version` 整数版本号用于并发控制的内容更新冲突检测。

### 陈旧传播

当 wiki 页面引用的源文档更新时，通过 `stale_since` 标记该页面为"已陈旧"，在知识图谱中传播依赖链。

### 可见性三档

- **private**：仅所有者可见
- **shared**：通过 share_token 分享链接访问
- **public**：通过 public_slug 公开访问（需配置 slug）
