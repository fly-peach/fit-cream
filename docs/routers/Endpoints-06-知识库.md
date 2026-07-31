# 知识库接口

prefix: `/knowledge-bases`

认证方式：普通用户操作为 JWT（get_current_user），管理员操作为 JWT（get_admin_user），公开/共享读取无认证。

## 知识库管理

### 创建

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases` |
| 认证 | 管理员 |

**请求体：KBCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-200 字符 |
| description | str | 默认 ""，最多 2000 字符 |
| schema_config | dict | 默认 {} |

**响应：`ResponseModel[KBOut]`**

### 列表（含订阅状态）

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[list[KBListOut]]`**

KBListOut：id, name, description, slug, owner_id, visibility, subscribed (bool), created_at

### 我的订阅

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/subscriptions` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[list[KBListOut]]`**

### 详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[KBOut]`**

### 更新

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/knowledge-bases/{kb_id}` |
| 认证 | 管理员 |

**请求体：KBUpdate**（name, description, schema_config 均为 Optional）

### 删除

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/knowledge-bases/{kb_id}` |
| 认证 | 管理员 |

**响应：`ResponseModel[None]`**

### 设置可见性

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/share` |
| 认证 | 管理员 |

**请求体：KBVisibilityUpdate**

| 字段 | 类型 | 约束 |
|------|------|------|
| visibility | str | private / shared / public |
| public_slug | Optional[str] | 最多 80 字符 |

可见性权限：private（仅订阅者可见）、shared（链接即权限）、public（所有人可见）。

---

## 订阅管理

### 订阅

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/subscribe` |
| 认证 | JWT 用户 |

逻辑：幂等（upsert 语义）。

**响应：`ResponseModel[KBSubscriptionOut]`** — id, kb_id, user_id, user_name, user_phone, subscribed_at

### 取消订阅

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/knowledge-bases/{kb_id}/subscribe` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[None]`**

### 订阅者列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/subscribers` |
| 认证 | 管理员 |

**响应：`ResponseModel[list[KBSubscriptionOut]]`**

### 移除订阅者

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/knowledge-bases/{kb_id}/subscribers/{user_id}` |
| 认证 | 管理员 |

---

## 文档管理

### 创建文档

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/documents` |
| 认证 | 管理员 |

**请求体：KBDocumentCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| title | str | 1-500 字符 |
| filename | str | 1-255 字符 |
| path | str | 默认 "/"，最多 500 字符 |
| source_kind | str | 默认 "wiki"，可选 raw / wiki |
| file_type | str | 默认 "md" |
| content | str | 默认 "" |
| tags | list[str] | 默认 [] |
| entity_type | Optional[str] | 最多 50 字符 |
| metadata | dict | 默认 {} |

逻辑：创建时自动对内容分块（chunk）并建立全文索引。

**响应：`ResponseModel[KBDocumentOut]`**

### 上传文档文件

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/upload` |
| 认证 | 管理员 |

**请求体：** multipart form-data

| 字段 | 类型 | 说明 |
|------|------|------|
| file | UploadFile | PDF/Word/PPT/HTML/Markdown 等 |
| path | str (Form) | 默认 "/" |
| source_kind | str (Form) | 默认 "raw" |
| tags | Optional[str] (Form) | 逗号分隔 |
| entity_type | Optional[str] (Form) | 实体类型 |

逻辑：使用 unstructured 解析器进行元素感知分块。

### 文档列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/documents` |
| 认证 | JWT 用户 |

**查询参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| source_kind | Optional[str] | — | raw / wiki |
| entity_type | Optional[str] | — | 实体类型过滤 |
| include_archived | bool | false | 是否包含已归档文档 |

**响应：`ResponseModel[list[KBDocumentListOut]]`** — 摘要输出（不含 content）

### 文档详情

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[KBDocumentOut]`** — 元数据不含内容

### 读取文档内容

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/content` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[KBDocumentContent]`** — id, title, filename, path, content, content_hash, version, updated_at

### 更新文档内容

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/content` |
| 认证 | 管理员 |

**请求体：KBDocumentContentUpdate**

| 字段 | 类型 | 说明 |
|------|------|------|
| content | str | 默认 "" |
| tags | Optional[list[str]] | 标签 |
| title | Optional[str] | 标题 |
| version | int | 乐观锁，必须匹配当前版本号 |

逻辑：触发自动重新分块 + 索引 + 过期传播。

### 更新文档元数据

| 项目 | 值 |
|------|-----|
| 方法 | PATCH |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` |
| 认证 | 管理员 |

**请求体：KBDocumentMetadataUpdate** — title, tags, entity_type, metadata, sort_order 均为 Optional

不触发重新分块。

### 删除文档

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}` |
| 认证 | 管理员 |

---

## 搜索

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/search` |
| 认证 | JWT 用户 |

**查询参数：**

| 参数 | 类型 | 默认 | 约束 |
|------|------|------|------|
| query | str | 必填 | 1-200 字符 |
| limit | int | 20 | 1-100 |

**响应：`ResponseModel[list[KBSearchResult]]`**

KBSearchResult：chunk_id, document_id, document_title, filename, path, chunk_index, content, header_breadcrumb, token_count, rank

引擎：PostgreSQL tsvector 全文搜索（GIN 索引），按 ts_rank 排序。

## 知识图谱

### 查询图谱

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/graph` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[KBGraphData]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| nodes | list | 节点（id, title, path, file_type, source_kind, tags） |
| edges | list | 边（source, target, type, page） |
| stats | dict | 统计信息 |

### 文档引用

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/documents/{doc_id}/references` |
| 认证 | JWT 用户 |

**响应：`ResponseModel[KBDocumentReferences]`** — cites, links_to, cited_by, linked_by

## 索引与维护

### 重新索引

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/reindex` |
| 认证 | 管理员 |

**响应：`ResponseModel[KBReindexResult]`** — kb_id, documents_processed, chunks_created, references

### 重建图谱

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/rebuild-graph` |
| 认证 | 管理员 |

### 健康检查

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/lint` |
| 认证 | 管理员 |

检测：未引用来源、过期页面、孤立反向链接。

## API Token 管理

### 创建 Token

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/knowledge-bases/{kb_id}/tokens` |
| 认证 | 管理员 |

**请求体：KBTokenCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | str | 1-100 字符 |
| scope | str | 默认 "read"，可选 read / write |
| expires_at | Optional[datetime] | 过期时间 |

**响应：`ResponseModel[KBTokenCreated]`**

| 字段 | 类型 | 说明 |
|------|------|------|
| token | str | 明文 Token（仅此一次返回） |
| token_out | KBTokenOut | 脱敏 Token 信息 |

存储：SHA256 哈希（不存原始值）。显示：仅存储前 12 字符用于识别。

### Token 列表

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/{kb_id}/tokens` |
| 认证 | 管理员 |

**响应：`ResponseModel[list[KBTokenOut]]`** — id, kb_id, token_prefix, name, scope, last_used_at, expires_at, revoked_at, created_at

### 撤销 Token

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/knowledge-bases/{kb_id}/tokens/{token_id}` |
| 认证 | 管理员 |

逻辑：软撤销（设置 revoked_at 时间戳）。

---

## 公开/共享读取（无认证）

### 共享知识库（链接即权限）

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/shared/{share_token}` |
| 认证 | 无 |

### 公开知识库

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/knowledge-bases/public/{public_slug}` |
| 认证 | 无 |

---

## MCP 集成

知识库通过 `fastapi-mcp` 框架暴露为 MCP 服务：

| 实例 | 挂载路径 | 操作数 | 认证方式 |
|------|----------|--------|----------|
| 用户 MCP | /mcp/user | 74 个操作（健身全域 + 知识库用户态） | 用户 API Key |
| 管理 MCP | /mcp/admin | 30 个操作（知识库管理） | JWT 管理员 |

每个端点设置了显式 `operation_id` 用于 MCP 工具暴露。
