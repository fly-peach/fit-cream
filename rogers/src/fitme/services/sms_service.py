"""阿里云 SMS 短信服务"""
import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class SmsService:
    @staticmethod
    async def send_code(phone: str, code: str) -> bool:
        """发送短信验证码"""
        if not settings.ALIBABA_CLOUD_ACCESS_KEY_ID:
            logger.info(f"[DEV] 短信验证码 {phone}: {code}")
            return True

        try:
            from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
            from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=settings.ALIBABA_CLOUD_ACCESS_KEY_ID,
                access_key_secret=settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            )
            config.endpoint = "dysmsapi.aliyuncs.com"
            client = DysmsapiClient(config)

            request = dysmsapi_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=settings.ALIBABA_CLOUD_SMS_SIGN_NAME,
                template_code=settings.ALIBABA_CLOUD_SMS_TEMPLATE_CODE,
                template_param=json.dumps({"code": code}),
            )
            response = client.send_sms(request)
            if response.body.code == "OK":
                return True
            logger.error(f"SMS send failed: {response.body.message}")
            return False
        except ImportError:
            logger.info(f"[DEV] 短信验证码(未安装SDK) {phone}: {code}")
            return True
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False
