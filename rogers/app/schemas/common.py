"""
统一响应格式

所有 API 接口使用 ResponseModel 包装返回值，
分页接口使用 PaginatedResponse。

格式约定：
- code=0 表示成功，非 0 为业务错误码（见 utils/exceptions.py）
- message 为人类可读的提示信息
- data 为实际业务数据
"""
from math import ceil
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一 API 响应包装"""

    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""

    items: List[T]
    total: int
    page: int
    size: int

    @property
    def total_pages(self) -> int:
        return ceil(self.total / self.size) if self.size > 0 else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages