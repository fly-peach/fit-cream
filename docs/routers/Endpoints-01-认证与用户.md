# 认证与用户接口

## 认证 (prefix: `/auth`)

### 注册

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/register` |
| 认证 | 无 |

**请求体：RegisterRequest**

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| phone | str | 11-20 字符 | 手机号 |
| password | str | 6-128 字符 | 密码（bcrypt 12 轮哈希） |
| name | Optional[str] | 最多 100 字符 | 显示名称 |

**响应：`ResponseModel[AuthResponseData]`**

AuthResponseData：

| 字段 | 类型 | 说明 |
|------|------|------|
| user | UserOut | 用户资料 |
| tokens | TokenPair | 双 Token |

TokenPair：

| 字段 | 类型 |
|------|------|
| access_token | str |
| refresh_token | str |
| token_type | str = "bearer" |
| expires_in | int |

错误：手机号重复 → 40001

### 登录

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/login` |
| 认证 | 无 |

**请求体：LoginRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| phone | str | 11-20 字符 |
| password | str | 必填 |

**响应：`ResponseModel[AuthResponseData]`**

错误：密码或用户不存在 → 40103

### 刷新令牌

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/refresh` |
| 认证 | 无 |

**请求体：RefreshRequest**

| 字段 | 类型 |
|------|------|
| refresh_token | str |

**响应：`ResponseModel[TokenPair]`**

逻辑：校验 refresh_token 类型 → 提取 user_id → 确认用户存在 → 生成全新的 TokenPair（令牌轮换，旧 token 不失效）。

---

## 用户 (prefix: `/users`)

### 获取个人信息

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/users/me` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[UserOut]`**

UserOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| phone | str | 手机号 |
| email | Optional[str] | 邮箱 |
| name | Optional[str] | 显示名称 |
| height_cm | Optional[float] | 身高 |
| weight_kg | Optional[float] | 体重 |
| age | Optional[int] | 年龄 |
| gender | Optional[str] | male / female / other |
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |
| role | str | user / admin |

### 更新个人信息

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/users/me` |
| 认证 | JWT (get_current_user) |

**请求体：UserUpdate**

| 字段 | 类型 | 约束 |
|------|------|------|
| name | Optional[str] | 最多 100 字符 |
| height_cm | Optional[float] | 0-300 |
| weight_kg | Optional[float] | 0-500 |
| age | Optional[int] | 1-150 |
| gender | Optional[str] | male / female / other |
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |

使用 `model_dump(exclude_unset=True)` 实现部分更新。

**响应：`ResponseModel[UserOut]`**
