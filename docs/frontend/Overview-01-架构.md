# 前端架构

## 技术栈

| 类别 | 技术 | 版本 |
|------|------|------|
| UI 框架 | React | ^19.2.6 |
| 语言 | TypeScript | ~6 |
| 构建工具 | Vite | ^8 |
| 路由 | react-router-dom | ^7.18.1 |
| 状态管理 | zustand | ^5.0.14 |
| 样式框架 | Tailwind CSS | ^4（CSS-first 配置） |
| UI 组件库 | shadcn/ui (base-nova 风格) + @base-ui/react | ^4.13.1 / ^1.6.0 |
| 图标 | lucide-react | ^1.25.0 |
| 动画 | motion | ^12.42.2 |
| 图表 | recharts | ^3.10.0 |
| 流程图 | @xyflow/react | ^12.11.2 |
| Markdown 渲染 | streamdown | ^2.5.0 |
| 语法高亮 | shiki | ^4.3.1 |
| 代码高亮 | @streamdown/code、@streamdown/math、@streamdown/mermaid、@streamdown/cjk | |
| SSE 流式 | 原生 fetch + AsyncGenerator | |
| AI SDK 类型 | ai (Vercel AI SDK) | ^7.0.34 |
| Token 用量 | tokenlens | ^1.3.1 |
| 日期处理 | date-fns | ^4.4.0 |
| Toast 通知 | sonner | ^2.0.7 |
| 字体 | Geist Variable | @fontsource-variable/geist |
| Rive 动画 | @rive-app/react-webgl2 | ^4.29.5 |

## 项目结构

```
frontend/src/
├── main.tsx                  # 入口：React 18 createRoot，包裹 ThemeProvider
├── App.tsx                   # BrowserRouter + 路由定义 + 授权守卫 + LanguageProvider + Toaster
├── index.css                 # Tailwind v4 CSS-first 配置 + 设计 Token + 暗色模式
│
├── pages/                    # 页面组件
│   ├── login.tsx             # 登录/注册页
│   ├── dashboard.tsx         # 今日概览仪表盘
│   ├── chat.tsx              # AI 教练对话页（流式）
│   ├── plans/                # 训练/饮食计划管理页（目录）
│   │   ├── index.tsx         # 主页面
│   │   ├── checkin-calendar.tsx # 锻炼/饮食日历
│   │   ├── day-detail-dialog.tsx # 训练日详情弹窗
│   │   ├── exercise-search.tsx # 动作内联搜索（防抖）
│   │   ├── diet-plan-card.tsx # 饮食计划卡片
│   │   └── types.ts          # 共享类型 + 常量
│   ├── diet.tsx              # 饮食记录页
│   ├── exercises.tsx         # 动作库浏览页（筛选 + 动图卡片）
│   ├── exercise-detail.tsx   # 动作详情页（中英双语）
│   ├── profile.tsx           # 个人资料编辑页
│   ├── knowledge-bases.tsx   # 知识库门户（订阅浏览）
│   ├── knowledge-base-detail.tsx # 知识库详情
│   ├── document-viewer.tsx   # 文档阅读页
│   └── admin/                # 管理员页面
│       ├── kb-management.tsx # 知识库管理后台
│       └── kb-detail.tsx     # 知识库管理详情
│
├── components/               # 组件
│   ├── ui/                   # shadcn/ui 基础组件（25 个）
│   ├── ai-elements/          # 购自 Vercel AI SDK 的 UI Kit(≈44 个文件)
│   ├── app-layout.tsx        # 应用壳（响应式侧边栏/底部导航）
│   ├── sidebar.tsx           # 聊天历史侧边栏
│   ├── theme-provider.tsx    # 主题切换（暗色/亮色/系统）
│   ├── admin-route.tsx       # 管理员路由守卫
│   ├── thread-history-item.tsx # 线程列表项（含内联改名）
│   ├── metadata-editor.tsx   # 元数据编辑/预览组件
│   └── kb-mcp-panel.tsx      # MCP 集成面板
│
├── hooks/                    # 自定义 Hooks
│   ├── use-threads.ts        # 线程列表管理
│   └── use-chat-sse.ts       # SSE 流式对话核心 Hook
│
├── stores/                   # Zustand 状态管理
│   ├── auth-store.ts         # 认证状态（Token/User/Logout）
│   └── chat-store.ts         # 聊天 UI 状态（当前线程/侧边栏）
│
├── lib/                      # 工具库
│   ├── api.ts                # 统一 API 客户端（请求/响应/错误处理）
│   ├── toast.ts              # sonner toast 封装（showError / showSuccess）
│   ├── kb-api.ts             # 知识库 API 封装（27 个方法）
│   ├── sse-client.ts         # SSE 流式客户端
│   ├── language-context.tsx  # 全局语言上下文（中英切换，localStorage 持久化）
│   ├── exercise-labels.ts    # 动作库标签中英文映射（肌群/器械/难度/目标）
│   └── meta-utils.ts         # 元数据工具函数
│
└── types/
    ├── chat.ts               # 聊天域类型定义（SSE 事件/消息/线程）
    └── exercise.ts           # 动作库类型定义（Exercise/统计）
```

## 构建与开发配置

**Vite 配置：**
- 插件：react()、tailwindcss()（Tailwind v4 Vite 插件）
- 路径别名：`@` → `./src`
- 开发服务器代理：`/api` → `http://localhost:8000`（changeOrigin: true）

**TypeScript 配置：**
- target: es2023，module: esnext，moduleResolution: bundler
- jsx: react-jsx，strict 模式
- 路径别名 `@/*` → `./src/*`
- `ai-elements` 目录排除在类型检查外

**ESLint：** 扁平配置，TypeScript + react-hooks + react-refresh 规则

**Prettier：** ^3.8.3，集成 prettier-plugin-tailwindcss

## 样式系统

- **Tailwind CSS v4**：CSS-first 配置（通过 `@tailwindcss/vite` 插件，无 tailwind.config.js）
- **设计 Token**：`:root` 使用 OKLCH 色值（翠绿/青色系，色相 ~155°），`.dark` 切换为中性灰度
- **暗色模式**：通过 `.dark` CSS class 控制（ThemeProvider 驱动）
- **shadcn/ui**：base-nova 风格，neutral 基础色，CSS 变量开启，lucide 图标
- **动画**：tw-animate-css 提供动画工具类
- **字体**：Geist Variable（无衬线可变字体）
