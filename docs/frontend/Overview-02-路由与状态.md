# 路由与状态管理

## 路由定义

使用 react-router-dom v7 的 `<BrowserRouter>` + `<Routes>` 定义。路由在 `App.tsx` 集中配置。

### 路由守卫

| 守卫 | 行为 |
|------|------|
| ProtectedRoute | `isAuthenticated` 为 false 时跳转 `/login` |
| AdminRoute | 未认证跳转 `/login`，角色非 admin 跳转 `/knowledge-bases` |

### 路由表

| 路径 | 页面组件 | 守卫 | 功能 |
|------|---------|------|------|
| `/login` | LoginPage | 无 | 登录/注册 |
| `/` | 重定向 → `/dashboard` | ProtectedRoute | 根路径 |
| `/dashboard` | DashboardPage | ProtectedRoute | 今日概览 |
| `/chat` | ChatPage | ProtectedRoute | AI 教练对话 |
| `/plans` | PlansPage | ProtectedRoute | 训练/饮食计划 |
| `/knowledge-bases` | KnowledgeBasesPage | ProtectedRoute | 知识库门户 |
| `/knowledge-bases/:kbId` | KnowledgeBaseDetailPage | ProtectedRoute | 知识库详情 |
| `/knowledge-bases/:kbId/documents/:docId` | DocumentViewerPage | ProtectedRoute | 文档阅读 |
| `/profile` | ProfilePage | ProtectedRoute | 个人资料 |
| `/admin/knowledge-bases` | AdminKbManagementPage | AdminRoute | 知识库管理后台 |
| `/admin/knowledge-bases/:kbId` | AdminKbDetailPage | AdminRoute | 知识库管理详情 |

### 应用壳

`AppLayout` 为全局布局组件，每个页面自行调用并包裹内容：
- 桌面：可收起的左侧导航栏（Logo + 5 个核心导航项 + 退出按钮）
- 移动端：顶部汉堡菜单（滑入抽屉）+ 底部 Tab 导航（5 项）
- 管理员额外可见"管理后台"导航项
- 聊天页独立管理右侧历史抽屉

## 状态管理（Zustand）

### useAuthStore

**持久化**：手动 localStorage（非 persist 中间件），key 为 `fitcream_token` / `fitcream_user`

| 状态 | 类型 | 说明 |
|------|------|------|
| token | string \| null | JWT Access Token |
| user | AuthUser \| null | 用户身份（id, role, name, phone） |
| isAuthenticated | boolean | 衍生状态 |
| logoutReason | string \| null | 被动登出原因 |

| 方法 | 功能 |
|------|------|
| setAuth(token, user) | 登录成功设置 Token + 用户 |
| setToken(token) | 仅设置/清除 Token |
| logout(reason?) | 清除 Token + 用户，记录登出原因 |
| clearLogoutReason() | 清除登出原因 |

### useChatStore

**持久化**：persist 中间件，id 为 `fitcream-chat`，仅持久化 `currentThreadId`

| 状态 | 类型 | 说明 |
|------|------|------|
| currentThreadId | string \| null | 当前活跃的线程 ID |
| sidebarOpen | boolean | 聊天侧边栏开/关 |

| 方法 | 功能 |
|------|------|
| setThreadId(id) | 切换当前线程 |
| setSidebarOpen(open) | 开关侧边栏 |
| toggleSidebar() | 切换侧边栏 |

## 认证流程

```
页面加载 → localStorage 读取 token
  → token 存在 → useAuthStore.setAuth() → 进入受保护路由
  → token 不存在 → 显示登录页

登录/注册 → POST /api/auth/{login|register}
  → 后端返回 UserOut + TokenPair
  → useAuthStore.setAuth(token, user)
  → 按角色重定向（admin → /admin/knowledge-bases, user → /knowledge-bases）

API 调用 → request() 拦截
  → HTTP 401 或 业务 code 401xx
  → useAuthStore.logout("登录已过期，请重新登录")
  → 登录页展示登出原因
```

### AuthUser 结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户 UUID |
| role | "user" \| "admin" | 角色 |
| name | string \| null | 显示名称 |
| phone | string \| null | 手机号 |
