from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo


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

    Assumes the caller separately verifies that the exchange is open on the
    calendar date. This function only enforces intraday time windows.
    """
    tz = ZoneInfo(timezone_name)
    local_now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    current = local_now.time().replace(tzinfo=None)

    market_open = time(9, 30)
    market_close = time(16, 0)
    exit_only = _parse_hhmm(exit_only_start)

    if current < market_open or current >= market_close:
        return SessionDecision(False, False, False, "Outside regular market hours.")

    if current >= exit_only:
        return SessionDecision(False, True, True, "Exit-only window.")

    start = _parse_hhmm(zero_dte_entry_start if is_zero_dte else normal_entry_start)
    end = _parse_hhmm(zero_dte_entry_end if is_zero_dte else normal_entry_end)

    if start <= current < end:
        return SessionDecision(True, True, False, "Entry window open.")

    return SessionDecision(False, True, False, "Monitoring window; new entries disabled.")
