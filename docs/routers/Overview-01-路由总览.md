# API 路由总览

## 路由注册

所有 API 路由统一在 `rogers/app/routers/__init__.py` 中注册，通过 `api_router` 在 `main.py` 中以 `settings.API_PREFIX`（默认为 `/api`）前缀挂载。

| 序号 | 路由模块 | 前缀 | 标签 | 说明 |
|------|---------|------|------|------|
| 1 | auth | `/auth` | auth | 注册/密码登录/短信验证码登录/刷新Token/验证码/密码管理 |
| 2 | users | `/users` | users | 用户资料 CRUD + 健康指标 |
| 3 | chat | `/chat` | chat | AI 对话（SSE 流式）+ 线程管理 |
| 4 | plans | `/plans` | plans | 训练计划 CRUD |
| 5 | diet_plans | `/diet-plans` | diet-plans | 饮食计划 CRUD |
| 6 | diet_meals | `/diet-meals` | diet-meals | 每餐记录 CRUD + 每日营养汇总 + 自定义食物 |
| 7 | checkins | `/checkins` | checkins | 打卡记录 CRUD + 连续打卡统计 |
| 8 | stats | `/stats` | stats | 训练统计 + 饮食趋势 |
| 9 | exercises | `/exercises` | exercises | 动作库查询 + 管理 CRUD + 分类/肌群/器械统计（1324 条中英双语 dataset） |
| 10 | knowledge_bases | `/knowledge-bases` | knowledge-bases | 知识库管理 |
| 11 | memory | `/memory` | memory | 语义记忆只读查询 |

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
| get_current_user | 多态：httpOnly Cookie JWT（浏览器）→ Header JWT（API 客户端）→ 用户 API Key | 先读 Cookie（`fitcream_access`），再解 Header Bearer JWT，最后尝试 API Key（sha256 哈希匹配） | 普通用户接口（App JWT / MCP API Key） |
| get_admin_user | get_current_user + role 校验 | user.role == "admin" | 管理员接口 |

所有 JWT 签名为 HS256，Access Token 有效期 7 天，Refresh Token 有效期 30 天，均写入 httpOnly Cookie（浏览器端 XSS 不可读）。
用户 API Key（一人一把）用于 MCP 外部接入，明文仅创建时返回一次，存储 sha256 哈希。

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
| ALIBABA_CLOUD_ACCESS_KEY_ID | "" | 阿里云 AccessKey（SMS + OSS 共用） |
| ALIBABA_CLOUD_SMS_SIGN_NAME | "" | 短信签名（未配置则开发日志输出验证码） |
| ALIBABA_CLOUD_SMS_TEMPLATE_CODE | "" | 短信模板 Code |
| OSS_ENDPOINT | oss-cn-hangzhou.aliyuncs.com | OSS 接入点 |
| OSS_BUCKET_NAME | "" | OSS Bucket（留空时聊天图片回退 base64） |
| OSS_SIGN_URL_EXPIRES | 1296000（15 天） | OSS 签名 URL 有效期(秒) |
| LOGIN_MAX_ATTEMPTS | 5 | 连续失败锁定阈值 |
| LOGIN_LOCK_MINUTES | 15 | 锁定时长(分钟) |
| VERIFICATION_CODE_COOLDOWN | 60 | 验证码发送冷却(秒) |
| VERIFICATION_CODE_MAX_PER_HOUR | 5 | 每手机号每小时验证码上限 |
| VERIFICATION_CODE_MAX_PER_IP_HOUR | 10 | 每 IP 每小时验证码上限 |
| SLOW_REQUEST_MS | 3000 | 慢请求阈值(毫秒)，超过则 access log 以 WARNING 高亮并标记 slow |

## HTTP 请求日志（RequestLoggingMiddleware）

记录每次非静态 HTTP 请求的 access log，并贯穿请求链路注入上下文：

| 行为 | 说明 |
|------|------|
| request_id 生成/透传 | 优先取请求头 `X-Request-ID`，否则生成 uuid 短串；写入 `request.state`、响应头 `X-Request-ID`，并经 ContextVar 贯穿该请求所有日志 |
| user_id 注入 | 认证路由（chat/message、chat/resume）在认证后写 `request.state.user_id`，access log 携带该字段 |
| 慢请求高亮 | 耗时 ≥ `SLOW_REQUEST_MS` 时以 WARNING 输出并标记 `slow`（JSON 格式加字段，文本格式加 `| SLOW` 标签） |
| 状态码高亮 | 状态码 ≥ 400 以 WARNING 输出 |
| 日志格式 | 由 `LOG_FORMAT` 控制：json（含 request_id/user_id/thread_id 字段）或 text（`[req=] [user=] [thread=]` 前缀） |

跳过的路径前缀：`/assets/`、`/favicon.ico`、`/robots.txt`。

## Docker 日志轮转

`docker-compose.yml` 为 db / app / backup 三个服务配置 `json-file` 日志驱动轮转：db 与 backup 单文件 10m、保留 3 份；app 单文件 20m、保留 5 份。
