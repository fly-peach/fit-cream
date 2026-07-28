# 用户服务

## AuthService

认证业务逻辑，位于 `src/auth/auth_service.py`。

| 方法 | 功能 | 逻辑 |
|------|------|------|
| register | 用户注册 | 校验 phone 唯一 → bcrypt 哈希密码 → 创建 User → 生成 TokenPair |
| login | 用户登录 | 按 phone 查用户 → bcrypt 验密码 → 生成 TokenPair |
| refresh_token | 刷新令牌 | verify_refresh_token 解码 → 查用户存活性 → 生成新 TokenPair |
| _generate_tokens | 生成令牌对 | 调用 create_access_token + create_refresh_token，封装 TokenPair |

### 注册逻辑

1. 检查 `phone` 是否已存在（存在则抛 40001）
2. `hash_password(password)` bcrypt 12 轮
3. 创建 `User(password_hash=hashed, phone=phone, name=name)`
4. `db.flush()` + `db.refresh(user)`（不 commit，交给 `get_db()` 依赖）
5. 生成并返回 TokenPair

### 登录逻辑

1. 按 phone 查询 `User`（不存在抛 40103）
2. `verify_password(password, user.password_hash)`（不匹配抛 40103）
3. 生成并返回 TokenPair

### 刷新令牌逻辑

1. `verify_refresh_token(token)` 解码 JWT
2. 校验 `type == "refresh"`
3. 提取 `sub = UUID(user_id)`
4. 查询 User 是否存在（不存在抛 40401）
5. 生成**全新的** TokenPair（令牌轮换）

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
| GET | /api/users/me | JWT | 获取当前用户资料 |
| PUT | /api/users/me | JWT | 更新个人资料 |

## 集成关系

```
AuthService.register/login
  └── 依赖 User model（查询/创建）
  └── 依赖 security.py（hash_password、verify_password、JWT）

AuthService.refresh_token
  └── 依赖 UserService.get_by_id()（确认用户仍存在）

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
