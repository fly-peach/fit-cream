# Agent 集成与 MCP

## Agent 工具集成

知识库通过两个 LangChain 工具暴露给 Agent ReAct 循环：

### search_knowledge_base

功能：在用户已订阅的知识库中进行全文搜索。

搜索流程：
1. 从 `RunnableConfig` 提取 `user_id`
2. 查询该用户的订阅列表（`kb_subscriptions` 表）
3. 如果指定了 `kb_id`，校验用户是否订阅并仅搜索该知识库
4. 如果未指定 `kb_id`，在所有已订阅知识库中搜索
5. 执行 PostgreSQL 全文搜索（chunk 级别）
6. 按 `ts_rank` 排序，合并结果
7. 返回结构化结果：chunk 内容、文档标题、面包屑、评分

返回结果限制：
- 每个知识库返回前 5 个结果
- 合并后返回前 20 个结果
- 每个 chunk 内容截断为 2000 字符

### read_kb_document

功能：读取指定文档的完整内容。

输入：`document_id`
返回：title、filename、content、tags、entity_type、file_type

## 系统 Prompt 集成

在 Agent 系统 Prompt 中，知识库搜索被定义为独立意图：

- **Intent 名称**：`knowledge_query`
- **触发关键词**：什么是、原理、为什么、知识、解释、区别、蛋白质、碳水、肌肥大、超负荷、代谢 等
- **行为规则**：
  - 当用户询问健身知识、训练原理、营养信息等专业问题时，先搜索知识库获取权威信息再回答
  - 如果需要完整上下文，调用 `read_kb_document` 获取全文
  - 回答时引用知识来源

## MCP (Model Context Protocol) 集成

知识库通过 `fastapi-mcp` 框架暴露为 MCP 服务，供外部 AI Agent（如 Cursor、Claude Desktop）接入。

### 双实例架构

| 实例 | 挂载路径 | 操作数 | 认证方式 |
|------|----------|--------|----------|
| 只读 MCP | /mcp/read | 13 个只读操作 | API Token 或 JWT |
| 管理 MCP | /mcp/admin | 31 个完整操作 | JWT 管理员 |

如果双实例挂载失败（fastapi-mcp 限制），回退为单个管理员 MCP 实例。

### 只读操作 (API Token 认证)

外部 Agent 可通过 API Token 接入只读 MCP，执行以下操作：

- 查询知识库列表
- 查看我的订阅
- 获取知识库详情
- 文档列表演示
- 文档全文读取
- 文档搜索
- 知识图谱查询
- 引用列表查看
- 订阅/取消订阅

### 管理操作 (JWT Admin 认证)

管理员可通过 JWT 执行完整 CRUD：

- 知识库：创建、更新、删除、设置可见性
- 文档：创建、上传、更新内容、更新元数据、删除
- 索引：全文重新索引、重建图谱
- 检查：执行 lint 检查
- 订阅管理：查看订阅者、移除订阅者
- Token 管理：创建、列表、撤销 API Token

### Token 管理

每个知识库可以创建多个 API Token，用于外部 MCP 访问：

- Token 权限范围：read / write
- 存储：SHA256 哈希（不存原始值）
- 显示：仅存储前 12 字符用于识别
- 安全性：支持设置过期时间、支持撤销
- 使用跟踪：记录最后使用时间

## 知识库与 Agent 整体集成架构

```
外部 Agent（Cursor/Claude Desktop）
    ↕ MCP（HTTP + API Token/JWT）
FastAPI MCP Server
    ↕
KnowledgeBaseService
    ↕
PostgreSQL（6 张知识库表 + TSVECTOR 全文搜索）
                              ↑
    内部 Agent ReAct 循环     │
    ├── search_knowledge_base │ （同进程直调 Service）
    └── read_kb_document      │
```

内部 Agent 通过 Qwen 模型 + 系统 Prompt 感知知识库搜索意图，在需要时自动调用搜索工具。外部 Agent 通过 MCP 协议直接接入知识库，无需登录 FitCream Web 界面。
