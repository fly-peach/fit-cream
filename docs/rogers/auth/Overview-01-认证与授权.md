# 认证与授权

## 认证体系

FitCream 支持手机号 + 密码登录与手机号 + 短信验证码登录，基于 JWT（HS256）实现无状态认证。短信验证码登录对未注册手机号自动注册。

### 注册/登录流程

```
客户端 -> POST /api/auth/register {phone, password, name?}
       -> AuthService.register()
         -> 校验手机号唯一性
         -> （可选）短信验证码校验（传入 verification_code 且阿里云 SMS 已配置时）-> 通过则 is_verified=True
         -> bcrypt 哈希密码（12 轮）
         -> 创建 User 记录（is_active=True, is_verified=False）
         -> 创建 UserSettings
         -> 记录审计日志（register）
         -> 生成 TokenPair（access_token + refresh_token）
       -> 返回 UserOut + TokenPair

客户端 -> POST /api/auth/login {phone, password}
       -> AuthService.login()
         -> 检查登录锁定（连续 5 次失败锁 15 分钟）
         -> 查询用户（按 phone）
         -> bcrypt 验证密码
         -> 检查 is_active / deleted_at
         -> 更新 last_login_at / last_login_ip
         -> 记录登录尝试（LoginAttempt）
         -> 记录审计日志（login）
         -> 生成 TokenPair
       -> 返回 UserOut + TokenPair
```

### 短信验证码登录

```
客户端 -> POST /api/auth/sms-login {phone, code}
       -> AuthService.sms_login()
         -> 检查登录锁定（与密码登录共用，防验证码暴力破解）
         -> 校验验证码（code_type="login"，原子消费 UPDATE）
            -> 验证失败：记录失败 attempt（单独提交）-> 抛 40000
         -> 手机号已注册 -> _finalize_login（状态校验 + 标记 is_verified + 更新登录信息 + 审计 action="login_sms"）
         -> 手机号未注册 -> _create_user（随机密码哈希、name="用户+尾号"、is_verified=True、审计 action="register_sms"）
         -> 生成 TokenPair
       -> 返回 UserOut + TokenPair
```

说明：sms_login 与 login 共用 `_check_login_lock` / `_finalize_login` / `_create_user`，避免逻辑漂移；验证码错误同样计入失败次数，触发锁定。

### 令牌刷新

```
客户端 -> POST /api/auth/refresh {refresh_token}
       -> AuthService.refresh_token()
         -> verify_refresh_token() 解码 JWT
         -> 校验 type == "refresh"
         -> 检查 jti 是否在黑名单（RefreshTokenBlacklist）
         -> 提取 sub（user_id）
         -> 确认用户存在且 is_active
         -> 生成全新的 TokenPair（令牌轮换）
       -> 返回 TokenPair
```

刷新时生成全新的 access_token 和 refresh_token。旧 refresh_token 可通过 logout 主动加入黑名单失效。

## JWT 设计

| 属性 | Access Token | Refresh Token |
|------|-------------|---------------|
| 签名算法 | HS256 | HS256 |
| 签名密钥 | JWT_SECRET（共享） | JWT_SECRET（共享） |
| 有效期 | 7 天 | 30 天 |
| Payload | sub (user_id), jti (uuid), iat (时间戳), type="access", exp | sub (user_id), jti (uuid), iat (时间戳), type="refresh", exp |
| 用途 | 身份认证 | 获取新的 Access Token |

Token 字段含 `jti`（JWT ID）和 `iat`（签发时间）。

### 安全说明

- 密钥 hardcoded 默认值（`your-super-secret-key-change-in-production-min-32-chars`）**必须**在 `.env` 中覆盖
- Access Token 有效期 7 天；如需更短可在 `ACCESS_TOKEN_EXPIRE_MINUTES` 配置
- 以下安全特性已通过安全增强实现（详见下方「安全增强」）

### 安全增强

- **账号状态**：User 模型新增 `is_active`（是否启用）和 `deleted_at`（软删除），`get_current_user` 依赖检查两者
- **登录锁定**：连续 5 次登录失败自动锁定 15 分钟（`LOGIN_MAX_ATTEMPTS` / `LOGIN_LOCK_MINUTES` 可配置），使用 `LoginAttempt` 表持久化
- **令牌黑名单**：logout 时将 refresh_token 的 jti 写入 `RefreshTokenBlacklist`，refresh 时检查黑名单拒绝已注销令牌
- **审计日志**：register/login/change_password 等敏感操作通过 `UserAuditLog` 记录（用户/操作/IP/UA）
- **短信验证码**：集成阿里云 SMS（`ALIBABA_CLOUD_*` 环境变量），支持注册/登录/密码重置场景发送验证码；未配置时开发环境跳过。验证码安全：`secrets.randbelow` 均匀生成 6 位码（避免 uuid4 首位弱熵）；原子消费（`UPDATE ... WHERE used_at IS NULL` 以 rowcount 判定，防并发重复使用）；双重限频（每手机号每小时 5 次 + 每 IP 每小时 10 次，防遍历手机号薅短信费用）；持久化记录 IP
- **密码管理**：新增 change_password（需旧密码验证）和 reset_password（验证码后重置）端点
- **手机验证**：`is_verified` 标志记录手机号验证状态

## 密码安全

- 哈希算法：bcrypt（12 轮）
- bcrypt 内在限制：输入密码截断为 72 字节
- 注册时 password 长度限制：6-128 字符

## 授权体系

### 角色

角色为简单的字符串字段（`user.role`），无 RBAC 表：

| 角色 | 值 | 说明 |
|------|-----|------|
| 普通用户 | "user" | 默认角色 |
| 管理员 | "admin" | 通过 seed 或在数据库中手动设置 |

### 认证依赖链

```
get_current_user
  → HTTPBearer 提取 Authorization: Bearer <token>
  → verify_access_token() 解码 JWT，校验 type
  → 查询 User 表（WHERE id = sub）
  → 检查 is_active（禁用则 403）
  → 检查 deleted_at（已删除则 401）
  → 返回 User ORM 实例

get_admin_user
  → get_current_user
  → 校验 user.role == "admin"
  → 不满足则抛 403

get_kb_from_token（知识库 MCP 专用）
  → 读取 Authorization: Bearer <token>
  → KnowledgeBaseService.verify_token() 校验 KB API Token
  → 返回 (token, kb) 元组
```

### 错误码

| 错误码 | 含义 | 使用场景 |
|--------|------|----------|
| 40001 | 手机号已存在 | register 时 phone 重复 |
| 40100 | 未授权 | 无 token 或 token 无效 |
| 40103 | 凭据无效 | login 时密码错误或用户不存在 |
| 40300 | 禁止访问 | 非管理员调用 admin 接口 |
| 40401 | 用户不存在 | refresh_token 时用户已被删除 |
| 40000 | BAD_REQUEST | 验证码发送过于频繁或已达上限 |
| 40300 | FORBIDDEN | 账号已被禁用 / 登录失败次数过多 |

所有业务异常统一返回 HTTP 200，在 `ResponseModel.code` 中携带错误码。

## Seed 管理员

在 FastAPI startup 时通过 `seed_admin()` 自动创建：

- 从环境变量读取 `SEED_ADMIN_PHONE` / `SEED_ADMIN_PASSWORD`
- 两个变量都为空时跳过
- 幂等逻辑：
  - 手机号已存在且 role 为 admin → 跳过
  - 手机号已存在且 role 非 admin → 升级为 admin
  - 手机号不存在 → 创建新用户（name="管理员"、role="admin"）
- 如果现有用户手机号与 `SEED_ADMIN_PHONE` 匹配，**每次启动**都会自动升级为 admin
