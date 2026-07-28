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
| user | UserOut | 用户资料（包含设置） |
| tokens | TokenPair | 双 Token |

TokenPair：

| 字段 | 类型 |
|------|------|
| access_token | str |
| refresh_token | str |
| token_type | str |
| expires_in | int |

错误：手机号重复 → 40001

逻辑：注册时自动创建默认用户设置。

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

### 修改密码

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/change-password` |
| 认证 | JWT (get_current_user) |

**请求体：ChangePasswordRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| old_password | str | 必填 |
| new_password | str | 6-128 字符 |

逻辑：验证旧密码 → 更新为新 bcrypt 哈希 → 记录审计日志。

### 登出

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/logout` |
| 认证 | 无 |

**请求体：LogoutRequest**

| 字段 | 类型 |
|------|------|
| refresh_token | str |

逻辑：解码 refresh_token → 提取 jti → 写入 RefreshTokenBlacklist。后续 refresh 时检查黑名单拒绝。

### 发送验证码

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/send-verification-code` |
| 认证 | 无 |

**请求体：SendVerificationCodeRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| phone | str | 11-20 字符 |
| code_type | str | register / login / reset_password，默认 register |

逻辑：检查冷却期（60秒）→ 检查每小时上限（5次）→ 生成 6 位验证码 → 阿里云 SMS 发送（未配置则开发日志输出替代）。

### 验证验证码

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/verify-code` |
| 认证 | 无 |

**请求体：VerifyCodeRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| phone | str | 11-20 字符 |
| code | str | 4-10 字符 |
| code_type | str | register / login / reset_password，默认 register |

逻辑：按 phone + code + code_type 查询 → 校验未使用且未过期 → 标记 used_at。

### 请求密码重置

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/request-password-reset` |
| 认证 | 无 |

**请求体：RequestPasswordResetRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| phone | str | 11-20 字符 |

逻辑：校验手机号已注册 → 发送重置密码验证码（code_type="reset_password"）。

### 重置密码

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/auth/reset-password` |
| 认证 | 无 |

**请求体：ResetPasswordRequest**

| 字段 | 类型 | 约束 |
|------|------|------|
| phone | str | 11-20 字符 |
| code | str | 4-10 字符 |
| new_password | str | 6-128 字符 |

逻辑：先验证验证码（code_type="reset_password"） → 将 user.password_hash 更新为新高哈希。

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
|------|------|
| id | UUID | 主键 |
| phone | str | 手机号 |
| email | Optional[str] | 邮箱 |
| name | Optional[str] | 显示名称 |
| age | Optional[int] | 年龄 |
| gender | Optional[str] | male / female / other |
| role | str | user / admin |
| settings | Optional[UserSettingsOut] | 用户设置 |

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
| age | Optional[int] | 1-150 |
| gender | Optional[str] | male / female / other |

使用 `model_dump(exclude_unset=True)` 实现部分更新。

**响应：`ResponseModel[UserOut]`**

---

## 用户设置 (prefix: `/users`)

### 获取用户设置

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/users/settings` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[UserSettingsOut]`**

UserSettingsOut：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |
| target_weight_kg | Optional[float] | 目标体重 |
| target_body_fat_pct | Optional[float] | 目标体脂 |
| weekly_training_goal | int | 每周训练次数目标 |
| calorie_goal | int | 每日卡路里目标 |
| protein_goal_g | int | 每日蛋白质目标(克) |
| carbs_goal_g | int | 每日碳水目标(克) |
| fat_goal_g | int | 每日脂肪目标(克) |
| notification_enabled | bool | 是否启用通知 |
| updated_at | DateTime | 更新时间 |

### 更新用户设置

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/users/settings` |
| 认证 | JWT (get_current_user) |

**请求体：UserSettingsUpdate**

| 字段 | 类型 | 约束 |
|------|------|------|
| goal | Optional[str] | lose_fat / gain_muscle / maintain / improve_health |
| target_weight_kg | Optional[float] | > 0 |
| target_body_fat_pct | Optional[float] | 0-100 |
| weekly_training_goal | Optional[int] | 1-14 |
| calorie_goal | Optional[int] | 500-10000 |
| protein_goal_g | Optional[int] | 0-500 |
| carbs_goal_g | Optional[int] | 0-1000 |
| fat_goal_g | Optional[int] | 0-300 |
| notification_enabled | Optional[bool] | - |

使用 `model_dump(exclude_unset=True)` 实现部分更新。

**响应：`ResponseModel[UserSettingsOut]`**

---

## 健康指标 (prefix: `/users`)

### 获取健康指标历史

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/users/health-metrics` |
| 认证 | JWT (get_current_user) |

**查询参数：**

| 字段 | 类型 | 默认 | 约束 |
|------|------|------|------|
| page | int | 1 | >= 1 |
| size | int | 20 | 1-100 |

**响应：`ResponseModel[PaginatedResponse[HealthMetricOut]]`**

### 获取最新健康指标

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/users/health-metrics/latest` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[Optional[HealthMetricOut]]`**

### 获取单条健康指标

| 项目 | 值 |
|------|-----|
| 方法 | GET |
| 路径 | `/api/users/health-metrics/{metric_id}` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[HealthMetricOut]`**

### 创建健康指标

| 项目 | 值 |
|------|-----|
| 方法 | POST |
| 路径 | `/api/users/health-metrics` |
| 认证 | JWT (get_current_user) |

**请求体：HealthMetricCreate**

| 字段 | 类型 | 约束 |
|------|------|------|
| measure_date | Date | 必填 |
| height_cm | Optional[float] | 0-300 |
| weight_kg | Optional[float] | 0-500 |
| body_fat_pct | Optional[float] | 0-100 |
| muscle_mass_kg | Optional[float] | 0-500 |
| chest_cm | Optional[float] | 0-500 |
| waist_cm | Optional[float] | 0-500 |
| hip_cm | Optional[float] | 0-500 |
| arm_cm | Optional[float] | 0-500 |
| thigh_cm | Optional[float] | 0-500 |
| note | Optional[str] | 最多 500 字符 |

逻辑：创建时自动计算 BMI 及分类。

**响应：`ResponseModel[HealthMetricOut]`**

### 更新健康指标

| 项目 | 值 |
|------|-----|
| 方法 | PUT |
| 路径 | `/api/users/health-metrics/{metric_id}` |
| 认证 | JWT (get_current_user) |

**请求体：HealthMetricUpdate**

所有字段可选。

逻辑：更新时如果 height 或 weight 变化，自动重新计算 BMI。

**响应：`ResponseModel[HealthMetricOut]`**

### 删除健康指标

| 项目 | 值 |
|------|-----|
| 方法 | DELETE |
| 路径 | `/api/users/health-metrics/{metric_id}` |
| 认证 | JWT (get_current_user) |

**响应：`ResponseModel[None]`**
