"""Pinned regular US equity schedule, including holidays and early closes.

XNAS is an exchange_calendars alias for XNYS. This is the QQQ regular-session
schedule, not SPXW overnight hours or a guarantee of future unscheduled closures.
"""
from datetime import timedelta
from functools import lru_cache
from importlib.metadata import version
from zoneinfo import ZoneInfo

import exchange_calendars as calendars

NY = ZoneInfo("America/New_York")


@lru_cache(maxsize=8)
def calendar(year):
    return calendars.get_calendar("XNAS", start=f"{year-1}-01-01", end=f"{year+1}-12-31")


def bounds(day):
    cal = calendar(day.year)
    label = day.isoformat()
    if not cal.is_session(label):
        return None
    return cal.session_open(label).to_pydatetime(), cal.session_close(label).to_pydatetime()


def session_at(now):
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timezone-aware observation required")
    day = now.astimezone(NY).date()
    hours = bounds(day)
    if hours is None or not hours[0] <= now < hours[1]:
        return None
    return {"date": day.isoformat(), "open": hours[0].isoformat(),
            "close": hours[1].isoformat(), "calendar": "XNAS (XNYS alias)",
            "calendar_version": version("exchange-calendars")}


def next_bar_close(end, seconds=300):
    hours = bounds(end.astimezone(NY).date())
    if hours is None or not hours[0] < end <= hours[1]:
        raise ValueError("Candle outside regular exchange session")
    if (end - hours[0]).total_seconds() % seconds:
        raise ValueError("Candle is not aligned to exchange open")
    if end < hours[1]:
        return end + timedelta(seconds=seconds)
    day = end.astimezone(NY).date() + timedelta(days=1)
    while bounds(day) is None:
        day += timedelta(days=1)
    return bounds(day)[0] + timedelta(seconds=seconds)


def validate_closes(ends, seconds=300):
    for i, end in enumerate(ends):
        next_bar_close(end, seconds)
        if i and end != next_bar_close(ends[i-1], seconds):
            raise ValueError("Missing exchange-session candle; do not forward-fill")
