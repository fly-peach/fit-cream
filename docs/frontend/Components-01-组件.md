# 组件

## App 级组件

### AppLayout（应用壳）

`components/app-layout.tsx`

响应式布局组件，所有受保护页面均包裹此组件：

| 平台 | 布局结构 |
|------|----------|
| 桌面 | 左侧可收起导航栏（Logo + 导航项：今日/AI 教练/训练计划/知识库/我的 + 管理员额外项 + 收起/退出） |
| 移动端 | 顶部栏（汉堡菜单滑入抽屉）+ 底部 Tab 导航（5 项） |

props：`{children, sidebarExtra?}` — sidebarExtra 用于聊天页的线程历史面板

### ThemeProvider

`components/theme-provider.tsx`

| 功能 | 说明 |
|------|------|
| 模式 | light / dark / system |
| 持久化 | localStorage（key: theme） |
| 快捷键 | `d` 键切换（输入框中不触发） |
| 跨 Tab 同步 | storage 事件监听 |
| CSS | 切换时添加 transition 控制，闪烁过渡 |

### AdminRoute

`components/admin-route.tsx`

路由守卫组件，校验 `useAuthStore` → role === "admin"，不满足时跳转 `/knowledge-bases`。

### Sidebar

`components/sidebar.tsx`

聊天历史侧边栏（新建对话按钮 + 线程列表），props 透传到 ThreadHistoryItem。

### ThreadHistoryItem

`components/thread-history-item.tsx`

单条线程项：显示标题/最后消息/时间/Token 数/消息数，支持内联改名（Enter 提交/Esc 取消/blur 提交）、删除。

### MetadataEditor / MetadataPreview

`components/metadata-editor.tsx`

元数据编辑（可编辑键值对行列表）和只读预览（徽章显示），用于 PlansPage 的自定义扩展字段。

### KbMcpPanel

`components/kb-mcp-panel.tsx`

MCP 集成面板。展示 `/mcp/admin` 管理端点信息、管理员 API Token 创建/列表/撤销。用户 MCP 接入（`/mcp/user`）请使用个人中心的 API Key 面板。

---

## UI 基础组件（shadcn/ui）

`components/ui/` 目录，共 25 个标准 shadcn/base-nova 组件：

accordion、alert、avatar、badge、button、button-group、card、carousel、collapsible、command（cmdk）、dialog、dropdown-menu、hover-card、input、input-group、popover、progress、scroll-area、select、separator、spinner、switch、tabs、textarea、tooltip

---

## Vendored ai-elements（Vercel AI SDK UI Kit）

`components/ai-elements/` 目录（约 44 个文件，排除在 TypeScript 检查范围外）

### 核心组件

| 组件 | 文件 | 功能 | 被使用方 |
|------|------|------|----------|
| Conversation | conversation.tsx | 聊天滚动容器（自动滚动） | ChatPage |
| Message | message.tsx | 消息块 + markdown 渲染（streamdown） | ChatPage、DocumentViewerPage |
| Reasoning | reasoning.tsx | 可折叠推理链显示 | ChatPage（InterleavedReasoning） |
| Tool | tool.tsx | 工具调用块（Header/Content/Input/Output） | ChatPage |
| Attachments | attachments.tsx | 附件列表/预览/移除 | ChatPage |
| PromptInput | prompt-input.tsx | 聊天输入框（含文件附件管理） | ChatPage |
| Context | context.tsx | Token 用量弹出层（tokenlens） | ChatPage |

### 渲染插件

| 插件 | 用途 |
|------|------|
| streamdown | 流式 Markdown 渲染引擎 |
| @streamdown/code | 代码块渲染（Shiki 语法高亮） |
| @streamdown/math | LaTeX 数学公式 |
| @streamdown/mermaid | Mermaid 图表 |
| @streamdown/cjk | CJK 文本间距优化 |

### 其他可用组件（未在页面中直接渲染）

agent、artifact、audio-player、canvas/node/edge/connection/controls/panel/toolbar（xyflow React Flow）、persona（Rive 动画）、terminal（ansi-to-react）、web-preview、sandbox、jsx-preview、task、response、suggestion、sources、inline-citation、transcription、speech-input、mic-selector、voice-selector、model-selector、plan、queue、chain-of-thought、checkpoint、commit、confirmation、file-tree、image、package-info、schema-display、shimmer、snippet、stack-trace、test-results、environment-variables、open-in-chat

---

## 分页特有子组件

| 组件 | 所属页 | 位置 | 功能 |
|------|--------|------|------|
| TodayTraining | DashboardPage | pages/dashboard.tsx | 今日训练卡片 |
| NutritionCard | DashboardPage | pages/dashboard.tsx | 营养环形图卡片 |
| ToolBlock | ChatPage | pages/chat.tsx | 工具调用内联渲染 |
| InterleavedReasoning | ChatPage | pages/chat.tsx | 推理链与工具调用交错渲染 |
| AgentTrace | ChatPage | pages/chat.tsx | ReAct 步骤流平铺渲染（type=tool 转 ToolCallCard，thought 展示推理增量） |
| ToolCallCard | ChatPage | pages/chat.tsx | 单条工具调用卡片（输入/输出/状态） |
| MemoryPanel | ChatPage | components/memory-panel.tsx | 「我的记忆」面板（语义记忆按分类分组卡片，支持刷新/重试/空态） |
| PlanQueuePanel | ChatPage | components/plan-queue-panel.tsx | 计划设计待办队列进度面板（顶部常驻，按 phase 分区 + 逐日待办状态，completed 可展开看当日方案表格） |
| DayDesignCard | ChatPage | components/day-design-card.tsx | 单日训练方案卡（动作表格 + 设计依据 + 确认按钮，确认发「[确认当日设计: <item_id>]」结构化消息） |
| MessageItem | ChatPage | pages/chat.tsx | 单条消息渲染（含角色/内容/元数据，历史图片按 metadata.images 渲染） |
| AttachmentItem | ChatPage | pages/chat.tsx | 图片附件缩略图 |
| ChatPromptInner | ChatPage | pages/chat.tsx | 聊天输入框内部（附件预览） |
| PromptInputAttachmentsDisplay | ChatPage | pages/chat.tsx | 输入框附件显示（memo 优化） |
| CheckinCalendar | PlansPage | pages/plans.tsx | 打卡日历（date-fns 月网格） |
| DayDetailDialog | PlansPage | pages/plans.tsx | 训练日详情弹窗 |
| DietPlanCard | PlansPage | pages/plans.tsx | 饮食计划卡片 |
| SyncPlanDialog | PlansPage | pages/plans/sync-plan-dialog.tsx | 训练日同步弹窗（月历选源日期 → 预览源日内容 → 确认同步到目标星期） |

## PlansPage 子文件

| 文件 | 组件 | 说明 |
|------|------|------|
| index.tsx | PlansPage | 主页面（含「同步计划」按钮） |
| checkin-calendar.tsx | CheckinCalendar | 锻炼/饮食日历切换 |
| day-detail-dialog.tsx | DayDetailDialog | 训练日详情弹窗 |
| exercise-search.tsx | ExerciseSearchInline | 动作内联搜索 |
| diet-plan-card.tsx | DietPlanCard | 饮食计划卡片 |
| sync-plan-dialog.tsx | SyncPlanDialog | 训练日同步弹窗 |
| types.ts | — | 共享类型 + 常量 + 日期工具函数 |
