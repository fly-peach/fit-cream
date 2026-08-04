# agent 记忆阈值与上下文精简文档同步

日期：2026-08-04
来源：代码审查（commit 2ed1cac / b62feee / c691ad1）
详情：记忆提取触发阈值从 20K 调整为 100K；每轮动态上下文精简为仅注入日期与用户称呼（身体数据/打卡/计划改为按需工具获取）；MemoryUpdate 接入共享 graph、consolidate 真实压缩。

## 待办

- [ ] Overview-01-架构.md：记忆提取触发阈值 20,000 → 100,000；调用流程中 _build_user_context 描述更新为精简版
- [ ] Overview-03-中间件管道.md：MemoryUpdateMiddleware 阈值 20,000 → 100,000
- [ ] Services-02-Memory系统.md：补语义记忆只读查询接口（GET /api/memory/semantic）；consolidate_memories 更新为真实压缩+LLM 升华
