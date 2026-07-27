"""
统一响应包装工具

提供 success() / error() 快捷函数，
用于在路由中快速构建标准格式的响应 dict。
"""
from typing import Any, Optional

from src.fitme.schemas.common import ResponseModel


def success(data: Any = None, message: str = "success") -> dict:
    """成功响应"""
    return ResponseModel(code=0, message=message, data=data).model_dump()


def error(code: int, message: str, data: Optional[Any] = None) -> dict:
    """错误响应"""
    return ResponseModel(code=code, message=message, data=data).model_dump()