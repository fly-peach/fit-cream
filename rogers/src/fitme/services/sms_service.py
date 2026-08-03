"""阿里云号码认证服务（短信认证）"""
import asyncio
import json
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# 短信认证走号码认证服务（dypnsapi），系统赠送签名/模板必须用该接口
_SMS_API_ENDPOINT = "dypnsapi.aliyuncs.com"


class SmsService:
    @staticmethod
    async def send_code(phone: str, code: str) -> bool:
        """发送短信验证码（系统赠送签名/模板，见 SendSmsVerifyCode）。"""
        if not settings.ALIBABA_CLOUD_ACCESS_KEY_ID:
            if settings.DEBUG:
                # 无凭证的 dev 模式：放行并打印验证码（生产环境禁止打印）
                logger.info(f"[DEV] 短信验证码 {phone}: {code}")
                return True
            logger.error("短信凭证未配置（ALIBABA_CLOUD_ACCESS_KEY_ID），生产环境拒绝放行")
            return False

        try:
            from alibabacloud_dypnsapi20170525.client import Client as DypnsapiClient
            from alibabacloud_dypnsapi20170525 import models as dypnsapi_models
            from alibabacloud_tea_openapi import models as open_api_models

            config = open_api_models.Config(
                access_key_id=settings.ALIBABA_CLOUD_ACCESS_KEY_ID,
                access_key_secret=settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET,
            )
            config.endpoint = _SMS_API_ENDPOINT
            client = DypnsapiClient(config)

            request = dypnsapi_models.SendSmsVerifyCodeRequest(
                phone_number=phone,
                sign_name=settings.ALIBABA_CLOUD_SMS_SIGN_NAME,
                template_code=settings.ALIBABA_CLOUD_SMS_TEMPLATE_CODE,
                template_param=json.dumps(
                    {
                        "code": code,
                        "min": str(settings.VERIFICATION_CODE_EXPIRE_MINUTES),
                    }
                ),
            )
            # SDK 为同步调用，放入线程池避免阻塞事件循环
            response = await asyncio.to_thread(client.send_sms_verify_code, request)
            if response.body.code == "OK" and response.body.success:
                return True
            logger.error(f"SMS send failed: {response.body.code} {response.body.message}")
            return False
        except ImportError as e:
            # 已配置凭证但 SDK 未安装：属于部署错误，不得伪造成功
            logger.error(f"SMS SDK 未安装但已配置凭证，发送失败: {e}")
            return False
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return False
