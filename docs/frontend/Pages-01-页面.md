# 页面

## LoginPage

| 项目 | 值 |
|------|-----|
| 路径 | `/login` |
| 守卫 | 无 |
| 认证状态 | 不支持已登录用户显示 |

登录页四模式切换：密码登录、短信验证码登录、注册、重置密码。支持分格验证码输入、密码显隐切换、装饰性动画背景与左侧品牌面板。登录成功根据 `user.role` 分别重定向到知识库门户或管理后台。

**API 调用：** `POST /api/auth/login`、`POST /api/auth/sms-login`、`POST /api/auth/register`、`POST /api/auth/send-verification-code`、`POST /api/auth/verify-code`、`POST /api/auth/request-password-reset`、`POST /api/auth/reset-password`

**依赖：** useAuthStore（setAuth, logoutReason, clearLogoutReason）

## DashboardPage

| 项目 | 值 |
|------|-----|
| 路径 | `/dashboard` |
| 守卫 | ProtectedRoute |

今日概览仪表盘。展示统计卡片（连续打卡天数、周训练次数、当前体重、累计数据）、今日训练卡片、营养环形图、周目标环形图、身体数据卡片、周训练时长柱状图（recharts）。

**子组件：** TodayTraining、NutritionCard

**API 调用：** `GET /stats/overview`、`GET /stats/weekly`、`GET /stats/body`、`GET /checkins?limit=50`

**依赖：** recharts、date-fns（zhCN 本地化）

## ChatPage

| 项目 | 值 |
|------|-----|
| 路径 | `/chat` |
| 守卫 | ProtectedRoute |

AI 健身教练对话页。支持 SSE 流式对话、推理链（Chain-of-Thought）内联显示、工具调用块渲染、图片附件（相册 + 摄像头，发送前自动上传 OSS 获取签名 URL 再提交）、Token 用量弹出层、线程历史侧边栏（重命名/删除）。

**子组件：** ToolBlock、InterleavedReasoning、MessageItem、AttachmentItem、ChatPromptInner

**使用 vendored ai-elements：** Conversation、Message、Reasoning、Tool、Attachments、PromptInput、Context

**API 调用：** `POST /api/chat/message`（SSE 流式）、`POST /api/chat/stop`、`POST /api/chat/upload-image`、`GET /api/chat/threads`、`GET /api/chat/threads/{id}/messages`、`PATCH /api/chat/threads/{id}/title`、`DELETE /api/chat/threads/{id}`、`DELETE /api/chat/history`

**依赖：** useChatSSE（流式 Hook）、useThreads（线程管理）、useChatStore（线程 ID 持久化）

## PlansPage

| 项目 | 值 |
|------|-----|
| 路径 | `/plans` |
| 守卫 | ProtectedRoute |
| 文件 | `src/pages/plans/`（目录，index.tsx 入口） |

训练与饮食计划管理页。实现打卡日历（锻炼/饮食双模式切换）、活跃训练计划详情（可编辑训练日与动作的 CRUD，搜索动作库）、饮食计划卡片（可编辑餐食与饮食日）。URL 编码选中日期（`/plans/exercise-plan-date=YYYY-MM-DD/diet-plan-date=YYYY-MM-DD`）。

**文件结构：**

| 文件 | 组件 | 说明 |
|------|------|------|
| index.tsx | PlansPage | 主页面（~280 行） |
| checkin-calendar.tsx | CheckinCalendar | 锻炼/饮食日历切换 |
| day-detail-dialog.tsx | DayDetailDialog | 训练日详情弹窗（编辑动作/训练日信息） |
| exercise-search.tsx | ExerciseSearchInline | 动作内联搜索（300ms 防抖自动搜索 + Enter 立即搜索） |
| diet-plan-card.tsx | DietPlanCard | 饮食计划卡片（餐食 CRUD） |
| types.ts | — | 共享类型 + 常量 + 日期工具函数 |

**数据流：** 所有 mutation 操作直接使用后端响应更新 state（后端 mutation 端点统一返回完整 PlanOut/DietPlanOut），不再额外发 GET 回捞。

**错误提示：** 使用 sonner toast（`showError` / `showSuccess`），全局 `<Toaster />` 挂载于 App.tsx。

**表单校验：** 动作编辑 sets∈[1,20]、reps∈[1,100]、weight≥0；训练日 rest_seconds≥0；添加餐食 food_name 非空、calories≥0。

**API 调用：** `GET /api/plans/active`、`POST /api/plans/{id}/days`、`PUT /api/plans/days/{id}`、`DELETE /api/plans/days/{id}`、`PUT /api/plans/exercises/{id}`、`DELETE /api/plans/exercises/{id}`、`POST /api/plans/days/{id}/exercises`、`GET /api/exercises?limit=12&keyword=`、`POST /api/checkins`、`GET /api/checkins/streak`、`GET /api/checkins?limit=200`、`GET /api/diet-plans/active`、`POST /api/diet-plans`、`POST /api/diet-plans/{id}/days`、`PUT /api/diet-plans/days/{id}`、`POST /api/diet-plans/days/{id}/meals`、`PUT /api/diet-plans/meals/{id}`、`DELETE /api/diet-plans/meals/{id}`

**依赖：** sonner（toast）、date-fns（zhCN 本地化）、MetadataEditor / MetadataPreview（元数据键值编辑）、DietRecordSection（饮食记录）

## ExercisesPage

| 项目 | 值 |
|------|-----|
| 路径 | `/exercises` |
| 守卫 | ProtectedRoute |

动作库浏览页。多条件筛选（肌群/身体部位/器械/难度/目标）+ 关键词搜索 + 卡片网格（缩略图 hover 切换动图 GIF 演示）+ 加载更多分页；点击卡片跳转详情页。页脚保留 Gym Visual 媒体署名。中英文标签随全局语言切换。

**API 调用：** `GET /api/exercises?...&limit=&offset=`、`GET /api/exercises/muscle-groups`、`GET /api/exercises/equipments`、`GET /api/exercises/categories`

**依赖：** useLanguage（中英切换）、exercise-labels（肌群/器械/难度/目标中文标签映射）

## ExerciseDetailPage

| 项目 | 值 |
|------|-----|
| 路径 | `/exercises/:id` |
| 守卫 | ProtectedRoute |

动作详情页。展示动图 GIF + 中英文名称 + 全标签（肌群/细分肌群/器械/难度/分类/目标）+ 描述 + 编号执行步骤 + 折叠的英文说明 + 每分钟消耗热量 + 媒体署名。

**API 调用：** `GET /api/exercises/{id}`

**依赖：** useLanguage、exercise-labels

## ProfilePage

| 项目 | 值 |
|------|-----|
| 路径 | `/profile` |
| 守卫 | ProtectedRoute |

个人资料编辑页。可编辑名称、年龄、身高、体重、性别、健身目标，实时显示 BMI。

**API 调用：** `GET /api/users/me`、`PUT /api/users/me`

## KnowledgeBasesPage

| 项目 | 值 |
|------|-----|
| 路径 | `/knowledge-bases` |
| 守卫 | ProtectedRoute |

知识库门户。支持全部/我的订阅双 Tab 切换，搜索过滤，订阅/取消订阅（乐观更新，失败回滚）。

**API 调用：** `GET /api/knowledge-bases`、`GET /api/knowledge-bases/subscriptions`、`POST /api/knowledge-bases/{id}/subscribe`、`DELETE /api/knowledge-bases/{id}/subscribe`

## KnowledgeBaseDetailPage

| 项目 | 值 |
|------|-----|
| 路径 | `/knowledge-bases/:kbId` |
| 守卫 | ProtectedRoute |

知识库详情页。多 Tab：文档阅读（列表 → 链接到 DocumentViewerPage）、全文搜索、知识图谱（节点/边列表，懒加载）、MCP 集成面板。

**子组件：** KbMcpPanel

**API 调用：** `GET /api/knowledge-bases/{id}`、`GET /api/knowledge-bases/{id}/documents`、`GET /api/knowledge-bases/{id}/search?query=&limit=`、`GET /api/knowledge-bases/{id}/graph`

## DocumentViewerPage

| 项目 | 值 |
|------|-----|
| 路径 | `/knowledge-bases/:kbId/documents/:docId` |
| 守卫 | ProtectedRoute |

文档只读阅读页。使用 ai-elements 的 MessageResponse 组件（streamdown）渲染 Markdown 内容。

**API 调用：** `GET /api/knowledge-bases/{kbId}/documents/{docId}/content`

## AdminKbManagementPage

| 项目 | 值 |
|------|-----|
| 路径 | `/admin/knowledge-bases` |
| 守卫 | AdminRoute |

知识库管理后台。创建/编辑/删除知识库（弹窗表单），设置可见性（private / shared / public + public_slug）。

**API 调用：** `GET /api/knowledge-bases`、`POST /api/knowledge-bases`、`PUT /api/knowledge-bases/{id}`、`DELETE /api/knowledge-bases/{id}`、`POST /api/knowledge-bases/{id}/share`

## AdminKbDetailPage

| 项目 | 值 |
|------|-----|
| 路径 | `/admin/knowledge-bases/:kbId` |
| 守卫 | AdminRoute |

知识库管理详情页。多 Tab：文档管理（创建/上传/编辑内容/删除，乐观锁 version 校验）、索引维护（重新索引+重建图谱，会触发长时间运行任务）、健康检查（lint 报告）、订阅者管理（列表/移除）、API Token 管理（创建/撤销，明文仅展示一次）。

**API 调用：** 所有 `kbApi.*` 中的管理接口
