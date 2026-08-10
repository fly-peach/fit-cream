"""
订阅 Pydantic Schema（KBSubscriptionOut）
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class KBSubscriptionOut(BaseModel):
    """订阅记录输出（管理员查看某 KB 的订阅者）"""
    id: UUID
    kb_id: UUID
    user_id: UUID
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    subscribed_at: datetime

    model_config = {"from_attributes": True}