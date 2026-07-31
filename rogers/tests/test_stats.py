"""统计路由 /api/stats/* 测试"""
from datetime import date

from tests.util import create_exercise, unwrap

TODAY = date.today().isoformat()


async def _seed_checkin(db_session, user):
    """通过服务层写入一条今日打卡，供统计端点聚合。"""
    from src.fitme.schemas.checkin import CheckinCreate, CheckinExerciseCreate
    from src.fitme.services.checkin_service import CheckinService

    ex = await create_exercise(db_session)
    data = CheckinCreate(
        date=date.today(),
        duration_min=45,
        actual_intensity="medium",
        mood=4,
        exercises=[CheckinExerciseCreate(exercise_id=ex.id, sets_done=3, reps_done=10)],
    )
    await CheckinService.create_checkin(db_session, user.id, data)
    await db_session.commit()


async def test_weekly_stats(user_client, db_session, user):
    await _seed_checkin(db_session, user)
    data = unwrap(await user_client.get("/api/stats/weekly"))
    assert isinstance(data, dict)


async def test_monthly_stats(user_client):
    data = unwrap(await user_client.get("/api/stats/monthly"))
    assert isinstance(data, dict)


async def test_body_stats(user_client):
    # 写入一条身体指标，body 统计应有身高体重
    await user_client.post(
        "/api/users/health-metrics",
        json={"measure_date": TODAY, "height_cm": 175, "weight_kg": 70},
    )
    data = unwrap(await user_client.get("/api/stats/body"))
    assert isinstance(data, dict)


async def test_overview_stats(user_client, db_session, user):
    await _seed_checkin(db_session, user)
    data = unwrap(await user_client.get("/api/stats/overview"))
    assert isinstance(data, dict)


async def test_diet_trend(user_client):
    data = unwrap(await user_client.get("/api/stats/diet"))
    assert isinstance(data, list)


async def test_stats_requires_auth(client):
    resp = await client.get("/api/stats/overview")
    assert resp.status_code in (401, 403)
