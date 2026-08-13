"""时区工具（Agent 时间上下文与工具默认日期的统一时区来源）。

所有"当前日期/当前时间"的取值统一走本模块，避免各处用服务器本地
date.today()/datetime.now() 造成跨时区错位（服务器多为 UTC，用户为 UTC+8）。

时区由 app.config.Settings.APP_TZ 配置，默认 Asia/Shanghai。
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import settings

_DEFAULT_TZ = "Asia/Shanghai"


def _tz() -> ZoneInfo:
    name = settings.APP_TZ or _DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(_DEFAULT_TZ)


def now() -> datetime:
    """当前时刻（APP_TZ 时区）。"""
    return datetime.now(_tz())


def today() -> date:
    """当前日期（APP_TZ 时区）。"""
    return now().date()


_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def format_now() -> str:
    """人类可读的当前时间字符串，如 2026-08-13 15:08（周四，Asia/Shanghai）。"""
    n = now()
    return f"{n:%Y-%m-%d %H:%M}（周{_WEEKDAYS[n.weekday()]}，{_tz().key}）"
