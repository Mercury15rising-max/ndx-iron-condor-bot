from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class ScheduledEvent:
    name: str
    starts_at: datetime


@dataclass(frozen=True)
class EventDecision:
    allow_entry: bool
    reason: str


def evaluate_event_risk(
    now: datetime,
    events: list[ScheduledEvent],
    block_before_minutes: int = 45,
    block_after_minutes: int = 30,
) -> EventDecision:
    for event in events:
        if event.starts_at.tzinfo is None and now.tzinfo is not None:
            event_time = event.starts_at.replace(tzinfo=now.tzinfo)
        else:
            event_time = event.starts_at

        start = event_time - timedelta(minutes=block_before_minutes)
        end = event_time + timedelta(minutes=block_after_minutes)
        if start <= now <= end:
            return EventDecision(
                False,
                f"Entry blocked around scheduled event: {event.name}.",
            )

    return EventDecision(True, "No blocked scheduled event window.")
