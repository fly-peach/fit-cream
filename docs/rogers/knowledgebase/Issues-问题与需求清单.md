# 知识库全链路问题与需求清单

> 触发事件：用户 0152（08:00 对话）问「我看一下我订阅的知识库呢」，Agent 回复"您目前还没有订阅任何知识库"；实际该用户已订阅「陈石b站up主」（40 文档/117 边，全部健身主题）。调查发现知识库中文检索双路失效，且 Agent 缺少"列出订阅"工具。本文档基于源码逐链路审查，整理完整问题与需求。

## 一、结论摘要

| 问题 | 级别 | 一句话 |
| --- | --- | --- |
| P0-1 中文全文检索失效 | P0 | `to_tsvector('simple')` + `websearch_to_tsquery('simple')` 不切中文词，中文 query 永远 0 命中 |
| P0-2 语义向量列生产缺失 | P0 | `init_db()` 被 `DEBUG` 门控，生产 `DEBUG=false` 永不补列，`kb_chunks.embedding` 不存在 → 语义路静默关闭 |
| P0-3 Agent 缺"列出订阅"工具 | P0 | Agent 拿 `search_knowledge_base` 硬凑列表请求 → 误报"没有订阅" |
| P0-4 订阅搜索排除 owner | P0 | `search_across_subscriptions` 只认订阅不认 owner，KB 所有者未订阅自己库时 Agent 搜索报"未订阅" |
| P1-1~P1-11 | P1 | 图谱 uncited/布局/着色、死代码、文档索引文案不符、缓存、跨库 N+1、重复文件名等 |
| P2-1~P2-10 | P2 | 运维、可观测性、体验优化项 |

## 二、已确认根因（本次 bug）

### P0-1 中文全文检索失效（搜索 0 命中的直接原因）

- 索引：`rogers/src/knowledge_base/models/chunk.py:51` — `Computed("to_tsvector('simple', content)", persisted=True)`
- 查询：`rogers/src/knowledge_base/services/search_service.py:32` — `func.websearch_to_tsquery("simple", query)`

PostgreSQL `simple` 配置只按空格/标点切词，**不做中文分词**。实测：`to_tsvector('simple', '减脂原理与热量缺口')` 输出 `'减脂原理与热量缺口':1`（整段一个 token）。因此 `search_vector @@ '健身'` 永远为假。40 篇健身文档对"健身" 0 命中即由此而来。

### P0-2 语义/向量路未启用（本可兜底，却整体关闭）

- 代码设计：`chunk.py:56-58` 定义 `embedding` 列，`semantic_available()`（`embeddings.py:51-69`）探测列存在才启用向量路，缺失时降级纯全文。
- 生产事实：`kb_chunks` 表无 `embedding` 列（information_schema 确认），`semantic_available()` 返回 `False`。
- 根因：`init_db()`（`rogers/app/database.py:239-241`）`if not settings.DEBUG: return`；而 `docker-compose.yml:33` 生产 `DEBUG: "false"`。因此 `_add_missing_columns`（补列逻辑）在生产**从未执行**，`embedding` 列从未被补上。全链路无 Alembic 迁移（见 P2-3），模型与生产 schema 漂移是系统性问题。

**P0-1 + P0-2 叠加 → 知识库搜索对任意中文 query 恒返回 0 → Agent 误判"未订阅/无内容"。**

### P0-3 Agent 缺"列出订阅"专用工具（产品层缺口）

- Agent 工具集只有 `search_knowledge_base` / `read_kb_document`（`src/agents/harness/tools/knowledge/knowledge_tools.py`）。
- 用户问"我订阅了什么"，Agent 只能 `search_knowledge_base(query="健身")` 替代，空结果被推理为"没订阅"。REST 有 `GET /knowledge-bases/subscriptions`，但 Agent 无对应工具。

### P0-4 订阅搜索范围遗漏 owner（权限不一致）

- `search_across_subscriptions`（`search_service.py:142-168`）未指定 `kb_id` 时只遍历 `list_my_subscriptions`（订阅表），**不包含用户 own 的 KB**；指定 `kb_id` 时 `if kb_id not in subscribed_ids: raise NotFoundException("未订阅知识库")`。
- REST 侧 `ensure_kb_access`（`knowledge_base_service.py:70-81`）明确放行 `owner_id == user_id`。工具与 REST 权限口径不一致：**KB 所有者若未自助订阅自己的库，Agent 无法搜索它**（admin 小佟此前搜"胸部训练"失败很可能也叠加了此因素）。

## 三、全链路问题清单

### A. 检索链路

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| A1 | 中文全文检索失效 | `chunk.py:51`, `search_service.py:32` | = P0-1 |
| A2 | 语义列生产缺失 + 无感知降级 | `embeddings.py:51-69`, `database.py:239` | = P0-2；`search_documents` 在 `semantic_available=False` 时静默返回纯全文，无日志/无降级标识，管理后台无从感知 |
| A3 | `semantic_available` 进程级缓存永不刷新 | `embeddings.py:48-49,60-68` | `_embedding_col_available` 进程内只探测一次。补列后必须重启才生效；反之列被删也会持续返回 True → 查询 500 |
| A4 | 跨库搜索 N+1 + 重复生成 query embedding | `search_service.py:134-140` | 对每个 KB 依次调 `search_documents`，每次重复探测 `semantic_available` 与调用 embedding 模型；query 向量应只算一次 |
| A5 | rerank 后处理器每次调用都重新实例化 | `embeddings.py:102-115` | `_load_reranker()` 无缓存，每次 search 都重建 `DashScopeRerank` |
| A6 | 向量路异常静默降级 | `search_service.py:69-70` | embedding 模型失败仅 `return fulltext[:limit]`，无 warning 日志；中文场景下纯全文又为空 → 结果空，难排查 |
| A7 | 全文字路中文结果无法补 | 同上 | `_rrf_fuse` 依赖两路都有召回；全文路对中文恒空，语义路关闭时 RRF/rerank 形同虚设 |
| A8 | 维度/模型漂移风险 | `chunk.py:57`, `config.py:79` | `Vector(1024)` 硬编码；若 `DASHSCOPE_EMBEDDING_MODEL` 换成非 1024 维模型（如 v1 1536 维），插入报维度错误，需重建列 |

### B. Agent 工具层

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| B1 | 缺"列出我的订阅/知识库"工具 | `knowledge_tools.py` | = P0-3；Agent 无法回答"我订阅了什么" |
| B2 | `read_kb_document.kb_id` 参数被忽略 | `knowledge_tools.py:87-92,109` | 参数描述"文档 ID 已含完整路径可不填"，实现完全没用 `kb_id`，仅按 `document_id` 查全局 UUID；语义混乱、无范围校验 |
| B3 | 0 结果消息误导推理 | `knowledge_tools.py:62-68` | `"知识库中未找到与「x」相关的内容"` 被 Agent 上升为"用户没有订阅任何知识库"；应在消息中区分"未订阅"与"无结果" |
| B4 | 跨订阅搜索默认 top5 单库 limit=5 | `search_service.py:143-168` | 多库时每库 5 条再合并取 5，细粒度召回可能被挤掉 |

### C. 权限与数据模型

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| C1 | 订阅搜索遗漏 owner | `search_service.py:142-168` vs `knowledge_base_service.py:70-81` | = P0-4 |
| C2 | `visibility` 字段代码/DB 漂移 | 全代码库无 `visibility`；生产 DB `knowledge_bases` 却有该列（「陈石b站up主」= private） | 模型未定义 → 无任何生效逻辑；若该字段承载"私有库不可发现"语义，则实际所有登录用户都能在"全部"列表看到并订阅 private 库。需确认列来源与预期语义（遗留列 or 待实现功能） |
| C3 | 无公开/匿名读路径，但无 visibility 约束 | `knowledge_bases.py` 路由 | 当前"登录即可读任意 KB 目录"，是否满足产品预期需确认 |
| C4 | 订阅无上限/防滥用 | `knowledge_base_service.py:109-125` | 轻量 |

### D. 文档入库 / 索引

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| D1 | 创建/更新文档不自动索引，且文案误导 | `document_service.py:27-57,96-118`；`knowledge_bases.py:216,287` | 接口 docstring 写"自动分块索引"/"自动重新分块 + 过期传播"，实际仅写行（`status=pending`），索引/引用图/向量需手动"重建并检查"。用户忘记点击则文档永远搜不到 |
| D2 | `propagate_staleness` 死代码 | `graph.py:252-271` 定义，全代码库无调用 | "过期传播"功能从未生效：文档更新后引用它的 wiki 页不会被打 `stale_since`，"已过期"徽标实际永不出现 |
| D3 | `archive_document` 死代码 | `document_service.py:139-145` | 软删除已实现但无路由暴露；前端删除是硬删（`delete_document`），被 wiki 引用时悬空引用由级联/重建兜底，但无提示 |
| D4 | 文档 `filename`+`path` 无唯一约束 | `document.py:38-40` | 重复文件名时引用解析 `setdefault` 首个胜出（`references.py:88-109`），后建文档被静默忽略；lint 无重复文件名检查 |
| D5 | 内容超长无前端/后端约束前置 | `chunk.py:71-73`, `chunker.py:20` | DB CHECK `length(content)<=10000`；超长硬截断兜底但无告警 |

### E. 图谱与引用

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| E1 | `uncited` 仅统计 cites 忽略 links_to | `graph.py:194-198` | `cited_ids` 只取 `reference_type=='cites'` 的 target；被 `links_to` 互链的节点全部误标"未引用"（已实证：全部节点红标） |
| E2 | 前端环形布局，非力导向 | `kb-graph.tsx:94,247-255` | `circularPosition` 按角度摆圆环，节点密集/重叠，无引力/斥力布局 |
| E3 | `_semantic_group` 分类规则过严 | `graph.py:32-47` | 仅按 `tags` 关键词匹配 5 组关键词；tags 不完整/不含关键词全部落"其他"灰色。未利用文档 content/entity_type |
| E4 | `get_graph` 全量返回无节点上限 | `graph.py:152-249` | full 模式全量节点/边，大型 KB 响应大；overview 降采样仅按 degree 截断，语义孤岛易被丢弃 |
| E5 | `find_uncited_sources` 与图节点 uncited 语义不一致 | `graph.py:318-335` vs `194-198` | 前者面向源文档（被 cites），后者面向所有节点（仅 cites）；前端展示易混淆 |

### F. 前端

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| F1 | 图谱 tab 数据缓存不刷新 | `knowledge-base-detail.tsx:75-85` | `if (graph) return` → 文档更新/重建后切 tab 仍是旧图，必须离开页面重进 |
| F2 | 搜索无结果提示误导 | `knowledge-base-detail.tsx:212-216` | 中文检索失效下恒显"未找到匹配内容"，掩盖底层故障；无"检索能力降级"提示 |
| F3 | 管理端文档列表/订阅者无分页 | `admin/kb-detail.tsx:236-277,336-372` | 大库渲染全量 DOM |
| F4 | 图谱节点详情面板无选中高亮 | `kb-graph.tsx:182-242` | 体验项 |

### G. 运维 / 可观测性

| 编号 | 问题 | 位置 | 说明 |
| --- | --- | --- | --- |
| G1 | 无 Alembic 迁移，模型/schema 漂移系统性 | `app/database.py` 全量依赖 `init_db`+`_add_missing_columns` | `DEBUG=false` 生产环境从不补列（P0-2 根因）；`visibility`（C2）同为漂移例 |
| G2 | 无中文分词扩展 | 生产 DB：仅 plpgsql/pg_trgm/vector | 治本需 `zhparser`/`pg_jieba` + 重建 `search_vector` + 重建 GIN 索引 |
| G3 | 回填脚本依赖列已存在 | `scripts/backfill_kb_chunk_embeddings.py:30-49` | `_require_vector_column` 列缺失直接退出，无自动补列步骤；运维必须先手动 `ALTER TABLE` |
| G4 | 检索降级无观测 | `embeddings.py`, `search_service.py` | 降级到纯全文/空结果均无日志与状态暴露，`get_index_status` 仅展示数量 |

## 四、需求文档（修复方案）

### R1【P0】中文检索可用（双管齐下）

- **R1a 启用语义路（主力，快）**
  1. 生产执行 `ALTER TABLE kb_chunks ADD COLUMN IF NOT EXISTS embedding vector(1024);`（或引入一次性迁移脚本统一处理）；
  2. 运行 `python scripts/backfill_kb_chunk_embeddings.py` 回填（现有脚本，幂等）；
  3. `semantic_available` 由"列存在"升级为"列存在 + 至少 N 个非空 embedding 或改为每库/按需探测"，并支持按 KB 维度的回退判定；
  4. `index_document` 保留现有"语义可用才写向量"逻辑（`indexer.py:44-64`），补列后新写入自动打向量；
  5. 全量 `rebuild-lint` 一次性补全存量。
- **R1b 引入中文分词（治本，DDL 风险较高）**
  - 安装 `zhparser`/`pg_jieba`，`search_vector` 生成式改为 `to_tsvector('zhparser', content)`，查询侧用 `to_tsquery('zhparser', ...)`；
  - 需重建 `kb_chunks.search_vector` 生成列 + `idx_kb_chunks_search` GIN 索引；建议与 R1a 分阶段上线，R1a 先行保证功能可用。

### R2【P0】Agent 补"列出订阅/知识库"能力

- 新增 `list_my_knowledge_bases` 工具（Agent 可调用），返回用户已订阅（含 owner）KB 的名称/ID/描述；
- `search_knowledge_base` 空结果消息区分三种情形：未订阅任何 KB / 已订阅但无命中 / 检索能力降级（见 R4），避免 Agent 误推理；
- 修复 P0-4：`search_across_subscriptions` 的范围 = `subscribed_ids ∪ {owned kb_id}`，与 `ensure_kb_access` 口径统一。

### R3【P1】图谱可视化修复

- **R3a uncited**：`cited_ids` 改为同时纳入 `links_to` 的 target（入边都算"被引用"），并让 `find_uncited_sources` 与节点标记语义对齐；
- **R3b 力导向布局**：前端接入 `d3-force`/`elkjs` 预计算布局（或 `@xyflow/react` 的 `dagre`/`elk` 适配），替换 `circularPosition`；
- **R3c 语义分组**：`_semantic_group` 增加 `entity_type`、title、content 关键词的加权匹配，并支持未知分组阈值回退，避免大面积"其他"。

### R4【P1】检索可观测性与降级提示

- `search_documents` 返回结构增加 `degraded: bool`（语义列缺失/模型失败/仅全文）与原因字段；
- 降级路径补 `logger.warning`；前端搜索 tab 在有降级时提示"检索能力降级，仅关键词匹配"；
- `get_index_status` 增加 `semantic_enabled` / `chunks_embedded` 有效性提示。

### R5【P1】文档入库语义对齐

- `create_document` / `update_document_content` 后自动触发（或异步任务触发）`index_document` + `rebuild_graph` 增量重建，去掉"需手动点击重建"的隐性步骤；或至少在返回中明确 `status=pending` 与下一步动作；
- 修正接口 docstring（去"自动分块索引/过期传播"误导文案）或补上真实行为；
- 启用 `propagate_staleness`（在 `update_document_content` 后对引用方打标），并补 lint 展示。

### R6【P1】数据模型收敛

- 决定 `visibility` 列去留：若保留，模型补列并在 list 接口实现"私有库仅 owner/订阅可见"；若弃用，出一次 DDL 清理遗留列；
- 引入 Alembic 或至少一套幂等 DDL 迁移脚本，替代"DEBUG 门控补列"，杜绝生产 schema 漂移（G1）；
- 文档 `filename+path` 增加唯一约束（或 lint 检查重复文件名）。

### R7【P2】性能与健壮性

- 跨库搜索：query embedding 只生成一次 + 各库 `search_documents` 并发执行（`asyncio.gather`）；
- `_load_reranker` 增加模块级缓存；
- `semantic_available` 缓存改为 TTL 或列变更后失效；
- 前端图谱 tab 切回时重新拉取；管理端文档/订阅者列表加分页。

### R8【P2】运维

- `backfill_kb_chunk_embeddings.py` 增加 `--ensure-column` 自动补列；
- 增加"知识库健康自检"入口：一次性报告 语义列可用性 / 中文分词可用性 / 未回填向量数 / 降级状态。

## 五、优先级与实施顺序建议

1. **第一步（P0，当天可做）**：R1a 补列 + 回填 + 重建 → 中文语义检索立即可用（覆盖 P0-1/P0-2/A1/A2/A6）；
2. **第二步（P0）**：R2 新增 Agent 列表工具 + 搜索范围含 owner + 空结果消息区分（覆盖 P0-3/P0-4/B1/B3/C1）；
3. **第三步（P1）**：R3 图谱三项修复（E1/E2/E3）+ R4 降级观测（A3/A7）+ R5 入库语义对齐（D1/D2）；
4. **第四步（P1/P2）**：R6 数据模型收敛（C2/G1/G2）+ R7 性能（A4/A5）+ R8 运维脚本（G3）。

## 六、生产运维手册（已随本批次代码落地）

> 以下命令在服务器上执行（可复用 sshpass 通道）。代码变更已包含：`backfill_kb_chunk_embeddings.py --ensure-column` 自动补列。

### 6.1 启用语义检索（R1a，P0）

```bash
cd /opt/fit-cream
# 1) 部署本批次代码并重启 app 容器
docker compose up -d --build app

# 2) 进入容器执行回填（列缺失时自动补列，随后回填全部 NULL 向量）
docker exec fitcream-app-1 python scripts/backfill_kb_chunk_embeddings.py --ensure-column
# 若容器名不同：docker ps 查 app 容器名

# 3) 全量重建索引 + 引用图 + lint（存量文档补齐 chunks/引用）
#    （或通过管理后台「知识库管理 -> 管理 -> 索引与检查 -> 重建并检查」）
curl -X POST "https://www.ice-cream.top/api/knowledge-bases/<kb_id>/rebuild-lint" \
  -H "Authorization: Bearer <admin-token>"
```

验证：`semantic_available` 为 TTL 缓存（300s），无需重启即生效；`GET /api/knowledge-bases/<kb_id>/index-status` 中 `chunks_pending_embedding` 应为 0。

### 6.2 引入中文分词（R1b，P1，DDL 风险）

```bash
# 1) 安装扩展（镜像需含 zhparser，若 pgvector 镜像无则需自建镜像/改用 pg_jieba）
CREATE EXTENSION IF NOT EXISTS zhparser;
-- 或 CREATE EXTENSION IF NOT EXISTS pg_jieba;

# 2) 生成列改为中文分词配置并重建 GIN 索引（需删除并重建生成列）
ALTER TABLE kb_chunks DROP COLUMN search_vector;
ALTER TABLE kb_chunks ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('zhparser', content)) STORED;
CREATE INDEX idx_kb_chunks_search ON kb_chunks USING gin (search_vector);
```

> R1b 建议与 R1a 分阶段上线：R1a 先保证中文语义检索可用，R1b 作为关键词路治本项。

### 6.3 数据模型收敛（R6，visibility 列）

```bash
# 确认 knowledge_bases.visibility 列来源与预期语义后二选一：
# A) 保留并实现：模型补列 + list 接口过滤（需代码配合）
# B) 弃用并清理：ALTER TABLE knowledge_bases DROP COLUMN IF EXISTS visibility;
```
