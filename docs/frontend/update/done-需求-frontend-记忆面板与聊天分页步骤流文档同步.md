# frontend 记忆面板与聊天分页步骤流文档同步

日期：2026-08-04
来源：代码审查（commit ed61aa5 / 03cc485 / a164767）
详情：聊天页新增「我的记忆」面板（语义记忆只读查询）；历史消息仅加载最近 10 条、向上滚动分页加载更早消息；SSE 新增 step 事件驱动的 Agent 步骤流可视化（AgentTrace）；历史图片展示。

## 待办

- [ ] Pages-01-页面.md：ChatPage 补「我的记忆」面板、历史分页加载、Agent 步骤流、历史图片
- [ ] Components-01-组件.md：补 MemoryPanel / AgentTrace / ToolCallCard 组件
- [ ] Services-01-服务层.md：补 useMemories hook；useChatSSE 事件分发补 step；sse-client 参数补 images
- [ ] Overview-01-架构.md：项目结构补 memory-panel.tsx、use-memories.ts、types/memory.ts
