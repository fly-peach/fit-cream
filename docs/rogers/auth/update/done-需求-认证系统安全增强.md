# auth 认证系统安全增强

**日期**：2026-07-28
**来源**：安全审查 / 对比 fit-cream-last
**详情**：当前认证系统缺少一些安全特性：用户状态管理、令牌黑名单、登录失败锁定、审计日志、阿里云短信服务支持。

## 待办

- [x] User 表新增 is_active 字段（Boolean，默认 True）
- [x] User 表新增 is_verified 字段（Boolean，默认 False）
- [x] User 表新增 deleted_at 字段（TIMESTAMPTZ，可空）
- [x] User 表新增 last_login_at 字段（TIMESTAMPTZ，可空）
- [x] User 表新增 last_login_ip 字段（VARCHAR(50)，可空）
- [x] 创建 RefreshTokenBlacklist 模型（jti + expires_at + revoked_at + reason）
- [x] 创建 LoginAttempt 模型（user_id + ip + attempt_at + success）
- [x] 创建 UserAuditLog 模型（user_id + action + ip + user_agent + created_at）
- [x] 创建 VerificationCode 模型（user_id + code + type + expires_at + used_at，支持短信/邮箱）
- [x] 更新 JWT 生成逻辑，添加 jti（JWT ID）和 iat（签发时间）
- [x] 创建 SmsService 封装阿里云 SMS 服务（发送验证码）
- [ ] 创建 EmailService 封装阿里云邮件推送服务（可选）
- [x] 更新 .env.example 添加阿里云配置（ALIBABA_CLOUD_ACCESS_KEY_ID、ALIBABA_CLOUD_ACCESS_KEY_SECRET、ALIBABA_CLOUD_SMS_SIGN_NAME、ALIBABA_CLOUD_SMS_TEMPLATE_CODE）
- [x] 更新 AuthService.register/login/refresh_token，记录审计日志
- [x] AuthService.login 新增登录失败计数与临时锁定逻辑（连续 5 次失败锁定 15 分钟）
- [ ] AuthService.register 新增发送短信验证码逻辑（可选配置开关）
- [x] AuthService 新增 send_verification_code 方法（阿里云短信）
- [x] AuthService 新增 verify_code 方法（验证短信/邮箱验证码）
- [x] AuthService 新增 request_password_reset 方法（发送验证码）
- [x] AuthService 新增 reset_password 方法（验证验证码后重置密码）
- [x] AuthService 新增 logout 方法（将 refresh_token 加入黑名单）
- [x] AuthService 新增 change_password 方法（用户修改密码，需验证旧密码）
- [ ] 创建 auth/security.py，独立 jwt/密码工具
- [x] 更新 get_current_user 依赖，检查 is_active 和 deleted_at
- [x] auth router 新增 POST /send-verification-code 端点
- [x] auth router 新增 POST /verify-code 端点
- [x] auth router 新增 POST /request-password-reset 端点
- [x] auth router 新增 POST /reset-password 端点
- [x] auth router 新增 POST /change-password 端点
- [x] auth router 新增 POST /logout 端点
- [x] 创建 auth schemas（SendVerificationCodeIn/VerifyCodeIn/RequestPasswordResetIn/ResetPasswordIn/ChangePasswordIn/LogoutIn）
- [ ] 更新 Database-01-用户表.md 文档
- [ ] 更新 Overview-01-认证与授权.md 文档
- [ ] 更新 Services-01-用户服务.md 文档
- [ ] 更新 Endpoints-01-认证与用户.md 文档
