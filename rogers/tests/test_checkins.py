"""打卡路由 /api/checkins/* 测试"""
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from tests.util import auth_headers, biz_code, create_exercise, create_user, unwrap

TODAY = date.today().isoformat()


async def _checkin_payload(exercise_id, **overrides):
    payload = {
        "date": TODAY,
        "duration_min": 45,
        "actual_intensity": "medium",
        "mood": 4,
        "exercises": [
            {"exercise_id": str(exercise_id), "sets_done": 3, "reps_done": 10, "weight_kg": 60}
        ],
    }
    payload.update(overrides)
    return payload


async def test_create_checkin(user_client, db_session):
    ex = await create_exercise(db_session)
    data = unwrap(await user_client.post("/api/checkins", json=await _checkin_payload(ex.id)))
    assert data["duration_min"] == 45
    assert len(data["exercises"]) == 1
    assert data["exercises"][0]["exercise_name"] == "杠铃卧推"


async def test_duplicate_checkin_same_day(user_client, db_session):
    ex = await create_exercise(db_session)
    payload = await _checkin_payload(ex.id)
    unwrap(await user_client.post("/api/checkins", json=payload))
    assert biz_code(await user_client.post("/api/checkins", json=payload)) == 40002


async def test_checkin_future_date_rejected(user_client, db_session):
    ex = await create_exercise(db_session)
    payload = await _checkin_payload(ex.id, date="2099-01-01")
    assert biz_code(await user_client.post("/api/checkins", json=payload)) == 40003


async def test_checkin_unknown_exercise(user_client):
    payload = {
        "date": TODAY,
        "duration_min": 30,
        "exercises": [{"exercise_id": str(uuid.uuid4()), "sets_done": 1, "reps_done": 1}],
    }
    assert biz_code(await user_client.post("/api/checkins", json=payload)) == 40000


async def test_list_and_date_filter(user_client, db_session):
    ex = await create_exercise(db_session)
    unwrap(await user_client.post("/api/checkins", json=await _checkin_payload(ex.id)))

    lst = unwrap(await user_client.get("/api/checkins"))
    assert lst["total"] == 1

    in_range = unwrap(
        await user_client.get("/api/checkins", params={"start": TODAY, "end": TODAY})
    )
    assert in_range["total"] == 1

    out_range = unwrap(
        await user_client.get(
            "/api/checkins", params={"start": "2000-01-01", "end": "2000-12-31"}
        )
    )
    assert out_range["total"] == 0


async def test_get_update_delete_checkin(user_client, db_session):
    ex = await create_exercise(db_session)
    created = unwrap(await user_client.post("/api/checkins", json=await _checkin_payload(ex.id)))
    cid = created["id"]

    got = unwrap(await user_client.get(f"/api/checkins/{cid}"))
    assert got["id"] == cid

    updated = unwrap(
        await user_client.put(f"/api/checkins/{cid}", json={"duration_min": 60, "mood": 5})
    )
    assert updated["duration_min"] == 60
    assert updated["mood"] == 5

    unwrap(await user_client.delete(f"/api/checkins/{cid}"))
    assert biz_code(await user_client.get(f"/api/checkins/{cid}")) != 0


async def test_streak(user_client, db_session):
    ex = await create_exercise(db_session)
    unwrap(await user_client.post("/api/checkins", json=await _checkin_payload(ex.id)))
    streak = unwrap(await user_client.get("/api/checkins/streak"))
    assert streak["current_streak"] >= 1
    assert streak["longest_streak"] >= 1
    assert streak["last_checkin_date"] == TODAY


async def test_checkin_validation(user_client):
    assert (
        await user_client.post("/api/checkins", json={"date": TODAY, "duration_min": 0})
    ).status_code == 422
    assert (
        await user_client.post(
            "/api/checkins", json={"date": TODAY, "duration_min": 30, "mood": 6}
        )
    ).status_code == 422


async def test_checkin_ownership(user_client, db_session):
    ex = await create_exercise(db_session)
    created = unwrap(await user_client.post("/api/checkins", json=await _checkin_payload(ex.id)))
    cid = created["id"]

    other = await create_user(db_session, phone="13700000003", name="其他用户")
    resp = await user_client.get(f"/api/checkins/{cid}", headers=auth_headers(other))
    assert biz_code(resp) != 0


async def test_checkin_today_uses_app_tz_not_server_local(monkeypatch, user_client, db_session):
    """应用时区（APP_TZ）的"今天"应被接受并计入连续打卡。

    修复前用服务器本地 date.today()：在 UTC 容器 + CST 凌晨窗口（tz_today() 比
    服务器本地日期晚一天）会把用户当天打卡误判为未来日期拒绝。此处固定时钟把
    tz_today() 设为比本机 date.today() 晚一天，等效该窗口；打卡必须成功且计入 streak。
    """
    from utils import timeutil

    ex = await create_exercise(db_session)
    app_today = date.today() + timedelta(days=1)
    fixed_now = datetime.combine(
        app_today, time(0, 30), tzinfo=ZoneInfo("Asia/Shanghai")
    )
    monkeypatch.setattr(timeutil, "now", lambda: fixed_now)

    unwrap(
        await user_client.post(
            "/api/checkins", json=await _checkin_payload(ex.id, date=app_today.isoformat())
        )
    )
    streak = unwrap(await user_client.get("/api/checkins/streak"))
    assert streak["last_checkin_date"] == app_today.isoformat()
    assert streak["current_streak"] >= 1


async def test_duplicate_race_maps_to_business_error(user_client, db_session, monkeypatch):
    """并发双写竞态：预检被绕过时 flush 触发唯一约束，应转 CHECKIN_ALREADY_EXISTS。"""
    from src.fitme.services.checkin_service import CheckinService

    ex = await create_exercise(db_session)
    payload = await _checkin_payload(ex.id)
    unwrap(await user_client.post("/api/checkins", json=payload))

    async def _no_precheck(*args, **kwargs):
        return None

    monkeypatch.setattr(CheckinService, "get_by_date", _no_precheck)
    assert biz_code(await user_client.post("/api/checkins", json=payload)) == 40002


async def test_checkin_aerobic_calories_estimated_by_minutes(user_client, db_session):
    """有氧动作（duration_min/distance_km）应按分钟速率估算热量，而非力量公式。"""
    ex = await create_exercise(db_session)
    data = unwrap(
        await user_client.post(
            "/api/checkins",
            json=await _checkin_payload(
                ex.id,
                exercises=[
                    {
                        "exercise_id": str(ex.id),
                        "duration_min": 30,
                        "distance_km": 5,
                    }
                ],
            ),
        )
    )
    assert data["calories_burned"] == 8.0 * 30
    assert data["exercises"][0]["duration_min"] == 30
    assert data["exercises"][0]["distance_km"] == 5
