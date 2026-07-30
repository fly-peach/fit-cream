"""阿里云 SMS 短信服务"""
import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class SmsService:
    @staticmethod
    async def send_code(phone: str, code: str) -> bool:
        """发送短信验证码"""
        if not settings.ALIBABA_CLOUD_ACCESS_KEY_ID:
            # 无凭证的 dev 模式：放行并打印验证码
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
            # SDK 为同步调用，放入线程池避免阻塞事件循环
            response = await asyncio.to_thread(client.send_sms, request)
            if response.body.code == "OK":
                return True
            logger.error(f"SMS send failed: {response.body.message}")
            return False
        except ImportError as e:
            # 已配置凭证但 SDK 未安装：属于部署错误，不得伪造成功
            logger.error(f"SMS SDK 未安装但已配置凭证，发送失败: {e}")
            return False
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False
