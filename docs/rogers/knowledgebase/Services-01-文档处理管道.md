# 文档处理管道

知识库文档从上传到可搜索，经历 解析 → 分块 → 索引 → 图谱构建 四个阶段。

## 解析

### 支持的格式

通过 `unstructured.partition.auto` 库支持多种文档格式：

- 原生支持：Markdown (.md, .markdown)、纯文本 (.txt)、reStructuredText (.rst)、HTML (.htm, .html)
- 可选依赖支持：PDF (.pdf)、Word (.docx)、PPT (.pptx)、Excel (.xlsx, .xls)、CSV (.csv)、JSON (.xml)、邮件 (.eml, .epub)

### 解析流程

1. **类型检测**：根据文件扩展名或显式 MIME 类型选择解析策略
2. **Frontmatter 提取**：解析 YAML frontmatter 作为元数据
3. **结构化元素提取**：调用 `unstructured.partition.auto` 将文档分解为结构化元素（Title、NarrativeText、ListItem、Table 等）
4. **Markdown 重建**：将结构化元素重新拼装为 Markdown 文本（`elements_to_markdown()`）
5. **标题提取**：优先级：frontmatter.title > 第一个 Title 元素 > 文件名

### 路径类型

- **Wiki 路径**（`/wiki/*`）：引用关系完整的维基风格文档，需要解析引用/链接
- **Raw 路径**（`/`）：纯内容文档，无引用关系解析

## 分块

### 分块策略

纯文本/Markdown 模式：

1. **段落分割**：以双换行（`\n\n`）为段边界
2. **标层面包屑**：追踪 Markdown 标题层级，构建面包屑路径（如 "训练 > 胸部 > 卧推"）
3. **目标块大小**：512 tokens
4. **块重叠**：128 tokens（段落级，非字符级）
5. **最小块**：32 tokens（低于此值的段落与相邻块合并）
6. **最大字符数**：10,000 chars（匹配数据库 CHECK 约束）
7. **超大块处理**：超过 10,000 chars 的块在句号边界拆分，最后硬截断

### CJK 感知的 Token 估计

中英文混合内容的 token 估算策略：

- 中文字符：约 1.5 chars/token
- 英文字符：约 4 chars/token
- 数字和标点：按英文处理

### Unstructured 元素感知模式

当文档通过 unstructured 库解析时，元素类型指导分块边界：

- Title 元素触发新块 + 更新面包屑
- NarrativeText 合并到当前块
- ListItem 合并到当前块
- Table 单独成块
- Footer、PageBreak、PageNumber 被跳过

## 索引

### 增量索引

`reindex_knowledge_base()` 处理整个知识库的重新索引：

1. 遍历所有文档
2. 比较 `content_hash` 与存储值
3. 仅对哈希变化或从未索引的文档重新分块
4. 在事务内：先 DELETE 旧 chunks，再 INSERT 新 chunks

### 原子性

分块替换在单事务中完成：旧块删除和新块插入使用同一数据库事务，确保一致性。

## 引用与图谱

### 引用解析流程

引用解析在索引时自动进行：

1. **Citation 引用**（`cites`）：
   - 匹配 `[^1]: filename.pdf` 格式的引用标记
   - 通过三层查找映射定位目标文档：文件名(+标题) / 去掉扩展名的文件名 / wiki 相对路径

2. **Wiki 链接**（`links_to`）：
   - 匹配 `[text](page.md)` 格式的交叉引用
   - 支持相对路径解析：`./`、`../`、`/wiki/xxx`、裸名称

3. **三层查找映射**：
   - 第一层：文件名（含标题）精确匹配
   - 第二层：去掉扩展名的文件名匹配
   - 第三层：wiki 相对路径匹配

### 陈旧传播

当源文档更新时，所有引用了该文档的 wiki 页面被标记为 `stale_since`，用于后续的 lint 检查。

## 格式检查 (Lint)

知识库 lint 检查包含：

- **未引用的源文档**：引用列表中不存在的源
- **陈旧页面**：引用的源已更新但自身未更新
- **失效链接**：wiki 链接指向不存在的页面
- **孤立页面**：无入链的页面
- **损坏的脚注**：脚注标记无法匹配

## 纯逻辑与 DB 编排分离

知识库的管道代码遵循清晰的架构分层：

- **纯逻辑层**（无数据库依赖）：chunker.py（分块算法）、parsers.py（文档解析）、references.py（引用解析）、lint.py（格式检查）
- **DB 编排层**（调用纯逻辑 + 数据库操作）：indexer.py（增量索引编排）、graph.py（图谱构建编排）、service.py（完整的 API 服务）
