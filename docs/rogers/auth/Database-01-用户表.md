# 用户表

## users — 用户表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK, default uuid4 | 主键 |
| phone | VARCHAR(20) | UNIQUE, NOT NULL, 索引 | 登录手机号 |
| email | VARCHAR(255) | UNIQUE, nullable | 可选邮箱 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 哈希 |
| name | VARCHAR(100) | nullable | 显示名称 |
| height_cm | NUMERIC(5,2) | nullable | 身高(cm) |
| weight_kg | NUMERIC(5,2) | nullable | 体重(kg) |
| age | INTEGER | nullable | 年龄 |
| gender | VARCHAR(10) | nullable | male / female / other |
| role | VARCHAR(20) | NOT NULL, default="user" | user / admin |
| goal | VARCHAR(50) | nullable | lose_fat / gain_muscle / maintain / improve_health |
| created_at | TIMESTAMPTZ | server_default=now() | 创建时间 |
| updated_at | TIMESTAMPTZ | server_default=now(), onupdate=now() | 更新时间 |

### 约束

- `phone` 唯一索引（登录标识）
- `email` 唯一索引（可选邮箱）
- 无 `is_active`、`is_verified`、`deleted_at` 等字段

### 关系

| 关系名 | 目标模型 | 级联 | 说明 |
|--------|----------|------|------|
| plans | Plan | CASCADE | 用户的训练计划 |
| diet_plans | DietPlan | CASCADE | 用户的饮食计划 |
| checkins | Checkin | CASCADE | 用户的打卡记录 |
| achievements | Achievement | CASCADE | 用户的成就 |
| knowledge_bases | KnowledgeBase | CASCADE | 用户创建的知识库 |
| conversations | Conversation | CASCADE | 用户的对话消息 |
| thread_metas | ThreadMeta | CASCADE | 用户的对话线程标题 |
| thread_usages | ThreadUsage | CASCADE | 用户的 token 用量 |

### 字段说明

- **phone**：唯一的登录标识，注册和登录均使用手机号（无邮箱登录）
- **password_hash**：bcrypt 12 轮哈希，输入密码截断 72 字节
- **name**：可选显示名称，未设置时在上下文中回退为"用户"
- **height_cm / weight_kg**：身体数据，用于 BMI 计算和计划生成
- **gender**：三选一（male / female / other），影响训练/饮食推荐的校准
- **role**：简单的字符串角色（user / admin），无 RBAC 表
- **goal**：用户健身目标，映射关系：
  - lose_fat → 减脂
  - gain_muscle → 增肌
  - maintain → 维持体型
  - improve_health → 改善健康

### Request Schemas

**UserUpdate** — 用户资料更新（所有字段可选）：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | VARCHAR(100) | max 100 | 显示名称 |
| height_cm | NUMERIC(5,2) | gt=0, le=300 | 身高 |
| weight_kg | NUMERIC(5,2) | gt=0, le=500 | 体重 |
| age | INTEGER | gt=0, le=150 | 年龄 |
| gender | VARCHAR(10) | regex: ^(male\|female\|other)$ | 性别 |
| goal | VARCHAR(50) | regex: ^(lose_fat\|gain_muscle\|maintain\|improve_health)$ | 目标 |

不支持修改 phone、email、password、role。

**UserOut** — 用户资料输出（排除 password_hash）：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | |
| phone | VARCHAR(20) | |
| email | VARCHAR(255) | nullable |
| name | VARCHAR(100) | nullable |
| role | VARCHAR(20) | |
| height_cm | NUMERIC(5,2) | nullable |
| weight_kg | NUMERIC(5,2) | nullable |
| age | INTEGER | nullable |
| gender | VARCHAR(10) | nullable |
| goal | VARCHAR(50) | nullable |
| created_at | TIMESTAMPTZ | |
