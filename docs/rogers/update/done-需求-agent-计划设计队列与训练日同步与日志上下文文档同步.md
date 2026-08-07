# agent+fitme plan 计划设计队列 + 训练日同步 + 请求日志上下文文档同步

日期：2026-08-07
来源：代码审查（未提交工作区改动）
详情：训练计划创建流程重构为「大纲 → 逐日协同设计 → 装配」的待办队列（PlanQueueMiddleware + plan_queue_tools + PlanQueuePanel/DayDesignCard），`create_plan_tool` 新增 `days` 直落库路径；新增 `sync_plan_day_tool` + `POST /plans/{plan_id}/copy-day` 训练日同步；logger/request_logging 引入 ContextVar 请求链路上下文（request_id/user_id/thread_id）、慢请求高亮（SLOW_REQUEST_MS）与 token 汇总摘要日志。

## 待办

- [x] agent/Services-01-工具系统.md：补 sync_plan_day_tool、计划设计待办队列工具组、create_plan_tool 的 days 直落库路径与工具计数
- [x] agent/Overview-03-中间件管道.md：中间件顺序表补 SkillsMiddleware/PlanQueueMiddleware，补 PlanQueueMiddleware 详情，AgentLoggingMiddleware 上下文注入说明
- [x] agent/Overview-01-架构.md：调用流程补 PlanQueueMiddleware 与 _log_usage_summary
- [x] fitme/Services-01-Service层.md：PlanService 补 copy_plan_day
- [x] routers/Endpoints-03-训练计划.md：补 POST /plans/{plan_id}/copy-day 端点
- [x] routers/Endpoints-02-聊天.md：SSE step 事件 type 补 reply；执行流程补 token 汇总摘要日志
- [x] routers/Overview-01-路由总览.md：配置表补 SLOW_REQUEST_MS；新增 HTTP 请求日志与 Docker 日志轮转章节
- [x] frontend/Components-01-组件.md：补 PlanQueuePanel / DayDesignCard / SyncPlanDialog 及 PlansPage 子文件
- [x] frontend/Pages-01-页面.md：ChatPage 补队列面板与 DayDesignCard、分页 8 条；PlansPage 补同步计划与 copy-day API
- [x] frontend/Services-01-服务层.md：useChatSSE step 分发补 reply
- [x] frontend/Overview-01-架构.md：项目结构补 sync-plan-dialog / plan-queue-panel / day-design-card，types/chat 补队列类型