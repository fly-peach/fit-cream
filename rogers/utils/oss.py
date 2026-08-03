"""
阿里云 OSS 对象存储工具

封装聊天图片上传：上传到私有路径（chat/{user_id}/{uuid}.{ext}），
设置 ACL 为私有，返回短期有效的签名 URL（默认 7 天，由 OSS_SIGN_URL_EXPIRES 控制）供访问 / 传给 DashScope 多模态接口。

未配置 OSS（缺少 AccessKey 等）时 is_oss_configured() 返回 False，
调用方应回退到 base64 data URL（开发模式）。
"""
import logging
from uuid import UUID, uuid4

import oss2
from oss2 import Auth, Bucket

from app.config import settings

logger = logging.getLogger("fitcream.oss")

CHAT_PATH_PREFIX = "chat"

# 扩展名映射：content_type -> 文件后缀
_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def is_oss_configured() -> bool:
    """OSS 是否已完整配置（用于开发模式回退判断）。"""
    return bool(
        settings.ALIBABA_CLOUD_ACCESS_KEY_ID
        and settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET
        and settings.OSS_ENDPOINT
        and settings.OSS_BUCKET_NAME
    )


def _get_bucket() -> Bucket:
    if not is_oss_configured():
        raise RuntimeError(
            "OSS 配置不完整，请检查环境变量 ALIBABA_CLOUD_ACCESS_KEY_ID / "
            "ALIBABA_CLOUD_ACCESS_KEY_SECRET / OSS_ENDPOINT / OSS_BUCKET_NAME"
        )
    auth = Auth(
        settings.ALIBABA_CLOUD_ACCESS_KEY_ID, settings.ALIBABA_CLOUD_ACCESS_KEY_SECRET
    )
    return Bucket(auth, settings.OSS_ENDPOINT, settings.OSS_BUCKET_NAME)


def _object_key(user_id: UUID | str, content_type: str, thread_id: str | None = None) -> str:
    ext = _CONTENT_TYPE_EXT.get(content_type, ".jpg")
    if thread_id:
        return f"{CHAT_PATH_PREFIX}/{user_id}/{thread_id}/{uuid4().hex}{ext}"
    return f"{CHAT_PATH_PREFIX}/{user_id}/{uuid4().hex}{ext}"


def _sign_url(bucket: Bucket, object_key: str, expires: int | None = None) -> str:
    if expires is None:
        expires = settings.OSS_SIGN_URL_EXPIRES
    url = bucket.sign_url("GET", object_key, expires)
    return url.replace("http://", "https://", 1)


def upload_chat_image(
    content: bytes,
    user_id: UUID | str,
    content_type: str = "image/jpeg",
    thread_id: str | None = None,
) -> str:
    """上传聊天图片到 OSS 私有路径，返回短期有效签名的完整 URL。

    聊天图片涉及用户隐私，ACL 设为私有；签名 URL 有效期由 settings.OSS_SIGN_URL_EXPIRES
    控制（默认 7 天），可直接嵌入前端或传给 DashScope。
    传入 thread_id 时图片归入 chat/{user_id}/{thread_id}/ 目录，便于按会话管理。
    """
    bucket = _get_bucket()
    object_key = _object_key(user_id, content_type, thread_id)

    bucket.put_object(object_key, content, headers={"Content-Type": content_type})
    bucket.put_object_acl(object_key, oss2.OBJECT_ACL_PRIVATE)

    return _sign_url(bucket, object_key)


def delete_object(object_key: str) -> bool:
    """删除 OSS 对象。"""
    try:
        bucket = _get_bucket()
        bucket.delete_object(object_key)
        return True
    except Exception:
        logger.exception("OSS 删除对象失败: %s", object_key)
        return False
