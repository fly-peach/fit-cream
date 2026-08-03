"""阿里云真实服务集成测试配置（独立于 tests/ 的数据库 conftest）。

只跑显式指定的目录，不参与普通测试套件。凭证一律经环境变量传入，不写入任何文件：

    set TEST_ALIBABA_ACCESS_KEY_ID=xxx
    set TEST_ALIBABA_ACCESS_KEY_SECRET=xxx
    set TEST_ALIBABA_SMS_PHONE=13800138000        # 接收真实短信的手机号
    set TEST_ALIBABA_SMS_SIGN_NAME=xxx             # 可选，覆盖 ALIBABA_CLOUD_SMS_SIGN_NAME
    set TEST_ALIBABA_SMS_TEMPLATE_CODE=SMS_xxx     # 可选，覆盖 ALIBABA_CLOUD_SMS_TEMPLATE_CODE
    set TEST_ALIBABA_OSS_BUCKET=xxx                # 可选，覆盖 OSS_BUCKET_NAME
    set TEST_ALIBABA_OSS_ENDPOINT=xxx              # 可选，覆盖 OSS_ENDPOINT

    pytest cloud_tests -v
"""
import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# 使 app / src / utils 可导入（cloud_tests 的上一级即 rogers/）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# TEST_ALIBABA_* 覆盖对应配置项；未设置的项沿用 .env 默认值
_OVERRIDES = {
    "ALIBABA_CLOUD_ACCESS_KEY_ID": "TEST_ALIBABA_ACCESS_KEY_ID",
    "ALIBABA_CLOUD_ACCESS_KEY_SECRET": "TEST_ALIBABA_ACCESS_KEY_SECRET",
    "ALIBABA_CLOUD_SMS_SIGN_NAME": "TEST_ALIBABA_SMS_SIGN_NAME",
    "ALIBABA_CLOUD_SMS_TEMPLATE_CODE": "TEST_ALIBABA_SMS_TEMPLATE_CODE",
    "OSS_BUCKET_NAME": "TEST_ALIBABA_OSS_BUCKET",
    "OSS_ENDPOINT": "TEST_ALIBABA_OSS_ENDPOINT",
}
for settings_key, test_key in _OVERRIDES.items():
    value = os.environ.get(test_key, "").strip()
    if value:
        os.environ[settings_key] = value

from app.config import settings  # noqa: E402,F401
