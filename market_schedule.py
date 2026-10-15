from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from exchange_session import session_at


@dataclass(frozen=True)
class SessionDecision:
    allow_new_entries: bool
    monitor_positions: bool
    exit_only: bool
    reason: str


def _parse_hhmm(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour=hour, minute=minute)


def evaluate_market_session(
    now: datetime,
    *,
    is_zero_dte: bool,
    timezone_name: str = "America/New_York",
    normal_entry_start: str = "10:00",
    normal_entry_end: str = "14:30",
    zero_dte_entry_start: str = "10:00",
    zero_dte_entry_end: str = "13:30",
    exit_only_start: str = "15:30",
) -> SessionDecision:
    """Decide whether the bot may enter, monitor, or only exit.

    Enforces the pinned regular-session calendar, holidays and early closes.
    Unscheduled closures still require a current external market-status check.
    """
    tz = ZoneInfo(timezone_name)
    session = session_at(now)
    if session is None:
        return SessionDecision(False, False, False, "Outside regular exchange session.")
    local_now = now.astimezone(tz)
    current = local_now.time().replace(tzinfo=None)

    # The same final half-hour exit policy applies to early-close sessions.
    calendar_exit = (datetime.fromisoformat(session["close"]) - timedelta(minutes=30)).astimezone(tz).time()
    exit_only = min(_parse_hhmm(exit_only_start), calendar_exit)

    if current >= exit_only:
        return SessionDecision(False, True, True, "Exit-only window.")

    start = _parse_hhmm(zero_dte_entry_start if is_zero_dte else normal_entry_start)
    end = _parse_hhmm(zero_dte_entry_end if is_zero_dte else normal_entry_end)

    if start <= current < end:
        return SessionDecision(True, True, False, "Entry window open.")

    return SessionDecision(False, True, False, "Monitoring window; new entries disabled.")

