# routers 语义记忆路由与聊天 SSE/OSS 文档同步

日期：2026-08-04
来源：代码审查（commit 58e2666 / a164767 / ed61aa5）
详情：新增 `/api/memory/semantic` 语义记忆只读查询路由；聊天 SSE 新增 `step` 事件（ReAct 步骤流）；OSS 签名 URL 有效期从约 100 年调整为 15 天（OSS_SIGN_URL_EXPIRES=1296000）；上传图片与历史消息支持过期 image_url 清理与历史图片展示；认证依赖链扩展为 Cookie JWT → Header JWT → API Key 多态。

## 待办

- [x] Overview-01-路由总览.md：路由注册表补 memory 路由；OSS_SIGN_URL_EXPIRES 默认值更新为 1296000（15 天）；认证依赖链补 Cookie JWT → Header JWT → API Key 多态说明
- [x] Endpoints-02-聊天.md：SSE 事件表补 step 事件（thought/tool/tool_result 三种 type）；上传图片 OSS URL 说明改为 15 天有效期 + 过期清理；补历史图片展示与 image_url 过期清理逻辑；MessageOut metadata 补 steps/images 说明
- [x] 新建 Endpoints-09-记忆.md：GET /api/memory/semantic 端点契约（category 过滤、响应字段、500 异常约定）
