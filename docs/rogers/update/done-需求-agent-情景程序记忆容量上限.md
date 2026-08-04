# agent 情景/程序记忆容量上限

日期：2026-08-04
来源：需求变更
详情：情景记忆与程序记忆此前无上限，随对话持续累加。为控制存储增长，为两类记忆设置每用户上限，超出上限按淘汰策略删除多余记录。

## 待办

- [x] store.py：新增 `_trim_memories` 裁剪方法（删除前清空 semantic 的 source_episodic_id 引用）
- [x] store_episodic：写入后按 重要性升序→时间升序 裁剪到 MEMORY_EPISODIC_MAX（默认 200）
- [x] store_procedural：写入后按 最久未使用→创建时间升序 裁剪到 MEMORY_PROCEDURAL_MAX（默认 50）
- [x] config.py / .env.example：新增 MEMORY_EPISODIC_MAX / MEMORY_PROCEDURAL_MAX 配置
- [x] Services-02-Memory系统.md：记录上限配置与淘汰策略
- [x] Overview-01-架构.md：关键配置常量表补情景/程序记忆上限
