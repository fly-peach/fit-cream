"""
活动水平换算路由 /api/activity-levels

- GET  /activity-levels            列出 4 档运动量水平
- POST /activity-levels/calculate  按档位 + 目标换算每日热量与宏量素目标
"""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services import activity_level_service
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/activity-levels", tags=["activity-levels"])


class ActivityLevelCalculateRequest(BaseModel):
    activity_level: Optional[str] = Field(
        default=None,
        description="活动档位：light / moderate / active / very_active",
    )
    goal: str = Field(
        default="lose_fat",
        pattern="^(lose_fat|gain_muscle|maintain|improve_health)$",
    )


@router.get("", response_model=ResponseModel[dict], operation_id="list_activity_levels")
async def list_activity_levels():
    """列出 4 档运动量水平及其活动系数。"""
    return ResponseModel(
        data={
            "levels": [
                {
                    "value": key,
                    "label": meta["label"],
                    "factor": meta["factor"],
                }
                for key, meta in activity_level_service.ACTIVITY_LEVELS.items()
            ],
            "default": activity_level_service.DEFAULT_ACTIVITY_LEVEL,
        }
    )


@router.post(
    "/calculate",
    response_model=ResponseModel[dict],
    operation_id="calculate_activity_targets",
)
async def calculate_activity_targets(
    data: ActivityLevelCalculateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """按当前用户身体数据 + 档位 + 目标换算每日热量与宏量素目标。"""
    body = await UserService.get_body_summary(db, user.id)
    targets = activity_level_service.compute_daily_targets(
        weight_kg=body.get("weight_kg"),
        height_cm=body.get("height_cm"),
        age=body.get("age"),
        gender=body.get("gender"),
        activity_level=data.activity_level,
        goal=data.goal,
    )
    return ResponseModel(data=targets)
