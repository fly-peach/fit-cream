"""阿里云 SMS 短信 + OSS 对象存储 真实服务集成测试。

需要真实凭证，未提供时整模块跳过。运行方式见 conftest.py 头注释。
"""
import base64
import os
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import httpx
import pytest

from app.config import settings

pytestmark = pytest.mark.skipif(
    not (
        settings.ALIBABA_CLOUD_ACCESS_KEY_ID
        and settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET
    ),
    reason="未配置阿里云 AccessKey（TEST_ALIBABA_ACCESS_KEY_ID / SECRET 或 .env）",
)

# 1x1 透明 PNG
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _skip_if_missing(name: str, value: str) -> None:
    if not value:
        pytest.skip(f"未设置 {name}")


async def test_sms_send_verification_code():
    """真实发送一条短信验证码，Alibaba 返回 code==OK 视为成功。"""
    from src.fitme.services.sms_service import SmsService

    phone = os.environ.get("TEST_ALIBABA_SMS_PHONE", "").strip() or settings.SEED_ADMIN_PHONE
    _skip_if_missing("TEST_ALIBABA_SMS_PHONE 或 SEED_ADMIN_PHONE", phone)
    assert settings.ALIBABA_CLOUD_SMS_SIGN_NAME, "短信签名未配置（.env 或 TEST_ALIBABA_SMS_SIGN_NAME）"
    assert settings.ALIBABA_CLOUD_SMS_TEMPLATE_CODE, "短信模板未配置（.env 或 TEST_ALIBABA_SMS_TEMPLATE_CODE）"

    ok = await SmsService.send_code(phone, "123456")
    assert ok is True


async def test_oss_upload_signed_url_and_delete():
    """上传图片到 OSS → 签名 URL 可访问且内容一致 → 删除后 URL 不可访问。"""
    from utils.oss import delete_object, upload_chat_image

    _skip_if_missing("OSS_BUCKET_NAME", settings.OSS_BUCKET_NAME)

    url = upload_chat_image(_PNG_1PX, uuid4(), "image/png")
    assert url.startswith("https://")

    # oss2 签名 URL 会对对象路径整体做 URL 编码（/chat%2F...），需解码还原
    object_key = unquote(urlsplit(url).path).lstrip("/")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        assert resp.status_code == 200
        assert resp.content == _PNG_1PX

        assert delete_object(object_key) is True

        resp = await client.get(url)
        assert resp.status_code in (403, 404), f"删除后仍可访问: {resp.status_code}"
