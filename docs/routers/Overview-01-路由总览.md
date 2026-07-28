# API 路由总览

## 路由注册

所有 API 路由统一在 `rogers/app/routers/__init__.py` 中注册，通过 `api_router` 在 `main.py` 中以 `settings.API_PREFIX`（默认为 `/api`）前缀挂载。

| 序号 | 路由模块 | 前缀 | 标签 | 说明 |
|------|---------|------|------|------|
| 1 | auth | `/auth` | auth | 注册/登录/刷新Token/验证码/密码管理 |
| 2 | users | `/users` | users | 用户资料 CRUD + 健康指标 |
| 3 | chat | `/chat` | chat | AI 对话（SSE 流式）+ 线程管理 |
| 4 | plans | `/plans` | plans | 训练计划 CRUD |
| 5 | diet_plans | `/diet-plans` | diet-plans | 饮食计划 CRUD |
| 6 | diet_meals | `/diet-meals` | diet-meals | 每餐记录 CRUD + 每日营养汇总 + 自定义食物 |
| 7 | checkins | `/checkins` | checkins | 打卡记录 CRUD + 连续打卡统计 |
| 8 | stats | `/stats` | stats | 训练统计 + 饮食趋势 |
| 9 | exercises | `/exercises` | exercises | 动作库查询 + 管理 CRUD + 分类/肌群统计 |
| 10 | knowledge_bases | `/knowledge-bases` | knowledge-bases | 知识库管理 |

## 响应格式

所有 API 端点统一使用 `ResponseModel<T>` 包装返回：

| 字段 | 类型 | 说明 |
|------|------|------|
| code | int | 0 表示成功，非 0 为业务错误码 |
| message | str | 可读消息，成功时为 "success" |
| data | Optional[T] | 实际数据载荷 |

业务异常全局捕获后**仍返回 HTTP 200**，在 `code` 中携带错误码。

## 错误码

### 通用

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 0 | SUCCESS | 成功 |
| 50000 | UNKNOWN_ERROR | 服务器内部异常 |

### 认证 (401xx)

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 40100 | UNAUTHORIZED | 未提供或无效的认证信息 |
| 40101 | INVALID_TOKEN | Token 格式错误/无效 |
| 40102 | TOKEN_EXPIRED | Token 已过期 |
| 40103 | INVALID_CREDENTIALS | 手机号或密码错误 |

### 权限 (403xx)

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 40300 | FORBIDDEN | 无权限（非管理员调用 admin 接口） |
| 40301 | RESOURCE_NOT_OWNED | 资源不属于当前用户 |

### 未找到 (404xx)

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 40400 | NOT_FOUND | 通用资源未找到 |
| 40401 | USER_NOT_FOUND | 用户不存在 |
| 40402 | PLAN_NOT_FOUND | 计划未找到 |
| 40403 | CHECKIN_NOT_FOUND | 打卡记录未找到 |
| 40404 | KB_NOT_FOUND | 知识库未找到 |
| 40405 | KB_DOCUMENT_NOT_FOUND | 知识库文档未找到 |

### 参数错误 (400xx)

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 40000 | BAD_REQUEST | 参数校验失败 |
| 40001 | EMAIL_ALREADY_EXISTS | 手机号已注册 |
| 40002 | CHECKIN_ALREADY_EXISTS | 当天已打卡 |
| 40003 | INVALID_DATE | 日期无效 |
| 40004 | INVALID_MOOD_RANGE | 心情评分超出 1-5 范围 |
| 40005 | UNSUPPORTED_FORMAT | 不支持的文件格式 |

### Agent (500xx)

| 错误码 | 常量 | 含义 |
|--------|------|------|
| 50001 | AGENT_ERROR | Agent 执行错误 |
| 50002 | TOOL_EXECUTION_ERROR | 工具调用失败 |
| 50003 | LLM_ERROR | LLM API 错误 |

## 认证依赖链

| 依赖 | 来源 | 校验方式 | 用途 |
|------|------|----------|------|
| get_current_user | Header `Authorization: Bearer <token>` | 解码 Access JWT → 查询 User | 普通用户接口 |
| get_admin_user | get_current_user + role 校验 | user.role == "admin" | 管理员接口 |
| get_kb_from_token | Header `Authorization: Bearer <token>` | KnowledgeBaseService.verify_token() | 知识库 MCP 外部访问 |

所有 JWT 签名为 HS256，Access Token 有效期 7 天，Refresh Token 有效期 30 天。

## 全局异常处理器

| 异常类型 | HTTP 状态码 | code | message |
|----------|-------------|------|---------|
| BusinessException | 200 | 业务错误码 | 业务描述 |
| UnsupportedFormatError | 200 | 40005 | 格式不支持 |
| RequestValidationError | 422 | 40000 | 参数校验失败 |
| Exception | 500 | 50000 | 服务器内部错误 |

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| API_PREFIX | `/api` | API 路由前缀 |
| JWT_SECRET | (env) | HS256 签名密钥 |
| ACCESS_TOKEN_EXPIRE_MINUTES | 10080 (7天) | Access Token 有效期 |
| REFRESH_TOKEN_EXPIRE_DAYS | 30 | Refresh Token 有效期 |
| CORS_ORIGINS | ["http://localhost:3000", "http://localhost:5173"] | 跨域允许来源 |
