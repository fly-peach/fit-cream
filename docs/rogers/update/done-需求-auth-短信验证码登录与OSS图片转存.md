# auth 短信验证码登录 + 聊天图片转存阿里云 OSS

**日期**：2026-07-30
**来源**：需求变更（commit 3b2e893）
**详情**：新增手机号 + 短信验证码登录（未注册手机号自动注册）；聊天图片上传转存阿里云 OSS 私有路径，返回长期有效签名 URL，未配置时回退 base64。登录页重构为四模式。

## 待办

### 认证 - 短信验证码登录

- [x] 新增 `POST /auth/sms-login` 端点（未注册手机号自动注册）
- [x] AuthService 新增 `sms_login` 方法，复用登录失败锁定防验证码暴力破解
- [x] 抽取 `_create_user` / `_finalize_login` / `_record_failed_attempt` 共用逻辑（register/login/sms_login 共用，避免漂移）
- [x] 失败 attempt 单独提交，修复异常回滚导致锁定计数丢失
- [x] 验证码原子消费（UPDATE ... WHERE used_at IS NULL，rowcount 判定，防并发重复使用）
- [x] 验证码改用 `secrets.randbelow` 均匀生成 6 位码（避免 uuid4 首位弱熵）
- [x] 发送端新增每 IP 每小时限频（VERIFICATION_CODE_MAX_PER_IP_HOUR=10，防遍历手机号薅短信）
- [x] VerificationCode 模型新增 ip 字段（索引）
- [x] RegisterRequest 新增可选 verification_code 字段（注册阶段即校验并标记 is_verified）

### 图片 - 聊天图片转存 OSS

- [x] 新增 `utils/oss.py`（阿里云 OSS 对象存储工具）
- [x] 聊天图片上传至 OSS 私有路径 `chat/{user_id}/{uuid}.{ext}`，ACL 设为私有
- [x] 返回长期有效签名 URL（OSS_SIGN_URL_EXPIRES 默认约 100 年）
- [x] 未配置 OSS 或上传失败时回退 base64 data URL（开发模式）
- [x] `POST /chat/upload-image` 响应 url 改为 OSS 签名 URL

### 前端

- [x] 登录页重构：验证码/密码/注册/重置四模式 + 分格验证码输入 + 品牌面板
- [x] 聊天发送前自动上传图片至 OSS 再以 URL 提交

### 配置

- [x] config.py 新增 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET / OSS_ENDPOINT / OSS_BUCKET_NAME / OSS_SIGN_URL_EXPIRES
- [x] config.py 新增 VERIFICATION_CODE_MAX_PER_IP_HOUR
- [x] .env.example 同步新增 OSS 与验证码 IP 限频配置

### 文档

- [x] Endpoints-01-认证与用户.md：新增 sms-login 端点，更新注册/发送验证码/验证验证码逻辑
- [x] auth/Overview-01-认证与授权.md：新增短信登录流程，扩展验证码安全增强说明
- [x] auth/Database-01-用户表.md：verification_codes 表补 ip 字段，audit_logs action 补 sms 类型
- [x] auth/Services-01-用户服务.md：方法表补 sms_login/_create_user/_finalize_login/_record_failed_attempt，新增短信登录逻辑段，API 表补 sms-login
- [x] Endpoints-02-聊天.md：upload-image 更新为 OSS 签名 URL + 回退说明
- [x] routers/Overview-01-路由总览.md：auth 描述补短信登录，配置参数补 OSS/验证码项
- [x] fitme/Services-01-Service层.md：AuthService 表补 sms_login 并引用 auth 文档
- [x] frontend/Pages-01-页面.md：LoginPage 更新四模式，ChatPage 补 OSS 上传
