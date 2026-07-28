# 认证与授权

## 认证体系

FitCream 使用手机号 + 密码登录，基于 JWT（HS256）实现无状态认证。

### 注册/登录流程

```
客户端 → POST /api/auth/register {phone, password, name?}
       → AuthService.register()
         → 校验手机号唯一性
         → bcrypt 哈希密码（12 轮）
         → 创建 User 记录
         → 生成 TokenPair（access_token + refresh_token）
       → 返回 UserOut + TokenPair

客户端 → POST /api/auth/login {phone, password}
       → AuthService.login()
         → 查询用户（按 phone）
         → bcrypt 验证密码
         → 生成 TokenPair
       → 返回 UserOut + TokenPair
```

### 令牌刷新

```
客户端 → POST /api/auth/refresh {refresh_token}
       → AuthService.refresh_token()
         → verify_refresh_token() 解码 JWT
         → 校验 type == "refresh"
         → 提取 sub（user_id）
         → 确认用户存在
         → 生成全新的 TokenPair（令牌轮换）
       → 返回 TokenPair
```

刷新时生成全新的 access_token 和 refresh_token。旧的 refresh_token **不失效**（无黑名单机制）。

## JWT 设计

| 属性 | Access Token | Refresh Token |
|------|-------------|---------------|
| 签名算法 | HS256 | HS256 |
| 签名密钥 | JWT_SECRET（共享） | JWT_SECRET（共享） |
| 有效期 | 7 天 | 30 天 |
| Payload | sub (user_id)、type="access"、exp | sub (user_id)、type="refresh"、exp |
| 用途 | 身份认证 | 获取新的 Access Token |

Token 字段不含 `jti`（JWT ID）和 `iat`（签发时间）。

### 安全说明

- 密钥 hardcoded 默认值（`your-super-secret-key-change-in-production-min-32-chars`）**必须**在 `.env` 中覆盖
- Access Token 有效期 7 天在生产环境中偏长
- Refresh Token 无撤销机制，有效期 30 天不可注销
- 无登录失败锁定机制

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
