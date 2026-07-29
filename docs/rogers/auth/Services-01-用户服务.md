# 用户服务

## AuthService

认证业务逻辑，位于 `src/auth/auth_service.py`。

| 方法 | 功能 | 逻辑 |
|------|------|------|
| register | 用户注册 | 校验 phone 唯一 → （可选）短信验证码校验 → bcrypt 哈希密码 → 创建 User（含 is_active/is_verified） → 创建 UserSettings → 记录审计日志 → 生成 TokenPair |
| login | 用户登录 | 检查登录锁定 → 按 phone 查用户 → bcrypt 验密码 → 检查 is_active/deleted_at → 更新 last_login_at/last_login_ip → 记录登录尝试 → 记录审计日志 → 生成 TokenPair |
| refresh_token | 刷新令牌 | verify_refresh_token 解码 → 检查 jti 黑名单 → 查用户存活性 → 生成新 TokenPair |
| change_password | 修改密码 | 验证旧密码 → bcrypt 哈希新密码 → 记录审计日志 |
| logout | 登出 | 解码 refresh_token → 将 jti 写入 RefreshTokenBlacklist |
| send_verification_code | 发送验证码 | 检查冷却期/每小时上限 → 生成 6 位验证码 → 持久化 → 调用 SmsService.send_code |
| verify_code | 验证验证码 | 按 phone + code + code_type 查询 → 校验未使用/未过期 → 标记 used_at |
| request_password_reset | 请求密码重置 | 校验手机号已注册 → 调用 send_verification_code(code_type="reset_password") |
| reset_password | 重置密码 | 调用 verify_code → 更新 password_hash |
| _check_login_lock | 登录锁定检查 | 查询最近 15 分钟内失败次数 → >= 5 次则抛 FORBIDDEN |
| _log_login_attempt | 记录登录尝试 | 创建 LoginAttempt（user_id/phone/ip/success） |
| _log_audit | 审计日志 | 创建 UserAuditLog（user_id/action/ip/user_agent） |

### 注册逻辑

1. 检查 `phone` 是否已存在（存在则抛 40001）
2. `hash_password(password)` bcrypt 12 轮
3. 创建 `User`（含 `is_active=True`、`is_verified=False`）
4. 创建 `UserSettings`（默认值）
5. 记录审计日志（`UserAuditLog` action="register"）
6. 生成并返回 TokenPair

### 登录逻辑

1. 检查登录锁定（`_check_login_lock`：最近 15 分钟内失败 >= 5 次则抛 40300）
2. 按 phone 查询 `User`（不存在抛 40103）
3. `verify_password(password, user.password_hash)`（不匹配抛 40103）
4. 检查 `is_active`（禁用则抛 40300）和 `deleted_at`（已删除则抛 40100）
5. 更新 `last_login_at` / `last_login_ip`
6. 记录登录尝试（`_log_login_attempt` success=True）
7. 记录审计日志（`_log_audit` action="login"）
8. 生成并返回 TokenPair

> 失败路径：步骤 2/3 失败时同样记录登录尝试（success=False）并记录审计日志。

### 刷新令牌逻辑

1. `verify_refresh_token(token)` 解码 JWT
2. 校验 `type == "refresh"`
3. 检查 `jti` 是否在 `RefreshTokenBlacklist` 中（已注销则抛 40100）
4. 提取 `sub = UUID(user_id)`
5. 查询 User 是否存在且 `is_active`（不存在抛 40401，禁用抛 40300）
6. 生成**全新的** TokenPair（令牌轮换）

## UserService

用户资料管理，位于 `src/fitme/services/user_service.py`。

| 方法 | 功能 | 逻辑 |
|------|------|------|
| get_by_id | 按 ID 查用户 | 查询 → 未找到抛 NotFoundException |
| get_by_email | 按邮箱查用户 | 返回 User 或 None |
| update_profile | 部分更新用户资料 | `model_dump(exclude_unset=True)` → setattr 逐字段更新 → flush + refresh |

### 更新资料逻辑

1. `UserService.get_by_id(user_id)` 获取现有用户
2. `data.model_dump(exclude_unset=True)` 仅保留前端提交的字段
3. 遍历字段，`setattr(user, field, value)`
4. `db.flush()` + `db.refresh(user)`

## Agent 集成

Agent 工具通过 LangChain `@tool` 装饰器定义，直接调用 UserService。工具使用 `async_session_factory()` 创建独立数据库会话（绕过 FastAPI 请求级 session）。

### get_user_profile_tool

| 属性 | 说明 |
|------|------|
| 功能 | 获取当前用户的身体数据和 BMI |
| 输入 | 无（user_id 从 RunnableConfig 提取） |
| 输出 | 用户全部资料字段 + 计算后的 BMI |
| 调用的 Service | UserService.get_by_id() |
| 额外逻辑 | BMI = weight / (height/100)² |

### update_user_profile_tool

| 属性 | 说明 |
|------|------|
| 功能 | 部分更新用户资料 |
| 输入 | name、height_cm、weight_kg、age、gender、goal（任意组合） |
| 输出 | 更新后的用户资料 |
| 调用的 Service | UserService.update_profile() |
| 提交策略 | 工具内主动 `db.commit()` |

## API 端点

| 方法 | 路径 | 认证 | 用途 |
|------|------|------|------|
| POST | /api/auth/register | 无 | 注册新用户 |
| POST | /api/auth/login | 无 | 登录 |
| POST | /api/auth/refresh | 无 | 刷新令牌 |
| POST | /api/auth/change-password | JWT | 修改密码（需旧密码） |
| POST | /api/auth/logout | 无 | 登出（加入黑名单） |
| POST | /api/auth/send-verification-code | 无 | 发送短信验证码 |
| POST | /api/auth/verify-code | 无 | 验证验证码 |
| POST | /api/auth/request-password-reset | 无 | 请求密码重置 |
| POST | /api/auth/reset-password | 无 | 重置密码 |
| GET | /api/users/me | JWT | 获取当前用户资料 |
| PUT | /api/users/me | JWT | 更新个人资料 |

## 集成关系

```
AuthService.register/login
  └── 依赖 User model（查询/创建）
  └── 依赖 security.py（hash_password、verify_password、JWT）

AuthService.refresh_token
  └── 依赖 UserService.get_by_id()（确认用户仍存在）
  └── 依赖 RefreshTokenBlacklist（检查 jti 黑名单）

AuthService.logout
  └── 依赖 RefreshTokenBlacklist（添加 jti）

AuthService.send_verification_code
  └── 依赖 SmsService（阿里云 SMS）
  └── 依赖 VerificationCode（持久化验证码）

UserService
  └── 依赖 User model

Agent Tools
  └── 依赖 UserService（同进程直调）
  └── 依赖 async_session_factory（独立 DB session）

get_current_user（FastAPI 依赖）
  └── 依赖 verify_access_token()
  └── 依赖 User model（SELECT）

get_admin_user（FastAPI 依赖）
  └── 依赖 get_current_user()
  └── 校验 user.role
```
