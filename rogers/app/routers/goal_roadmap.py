"""
目标闯关路线图路由 /api/goal-roadmap/*

- GET /goal-roadmap：当前用户的 active 路线图（含里程碑）+ 当前关 + 最新力量基线 + 最新身体指标。
  供前端训练计划页（完整路线图）与 Dashboard（当前关节点）读取。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from src.fitme.models.user import User
from src.fitme.schemas.common import ResponseModel
from src.fitme.services.goal_service import (
    GoalRoadmapService,
    PerformanceTestService,
    roadmap_to_dict,
)
from src.fitme.services.user_service import UserService

router = APIRouter(prefix="/goal-roadmap", tags=["goal-roadmap"])


@router.get("", response_model=ResponseModel[dict], operation_id="get_goal_roadmap")
async def get_goal_roadmap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的闯关路线图（active）+ 当前关 + 最新基线与身体指标。"""
    roadmap = await GoalRoadmapService.get_active_roadmap(db, user.id)

    current = None
    if roadmap:
        for m in roadmap.milestones:
            if m.status == "active":
                current = m
                break

    tests = await PerformanceTestService.get_latest_tests(db, user.id)
    health = await UserService.get_latest_health_metric(db, user.id)

    body_metrics = {
        "weight_kg": float(health.weight_kg) if health and health.weight_kg is not None else None,
        "height_cm": float(health.height_cm) if health and health.height_cm is not None else None,
        "body_fat_pct": float(health.body_fat_pct) if health and health.body_fat_pct is not None else None,
        "waist_cm": float(health.waist_cm) if health and health.waist_cm is not None else None,
    }

    return ResponseModel(
        data={
            "roadmap": roadmap_to_dict(roadmap) if roadmap else None,
            "current_milestone": {
                "id": str(current.id),
                "stage_index": current.stage_index,
                "title": current.title,
                "exit_criteria": current.exit_criteria,
                "expected_weeks": current.expected_weeks,
                "status": current.status,
            }
            if current
            else None,
            "latest_tests": tests,
            "body_metrics": body_metrics,
        }
    )
