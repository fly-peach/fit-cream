"""
独立心情记录 Schemas

定义心情记录的请求/响应模型：
- MoodUpsert: 按日期 upsert 的请求（同日覆盖）
- MoodOut: 心情记录输出
"""
from datetime import date as date_type
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MoodUpsert(BaseModel):
    """记录/更新心情请求（按日期 upsert）"""

    date: date_type = Field(description="记录日期")
    mood: int = Field(ge=1, le=5, description="心情评分 1-5")
    note: Optional[str] = Field(default=None, max_length=500)


class MoodOut(BaseModel):
    """心情记录输出"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    date: date_type
    mood: int
    note: Optional[str] = None
    created_at: datetime
