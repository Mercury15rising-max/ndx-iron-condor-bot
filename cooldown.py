from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class CooldownDecision:
    allow_entry: bool
    reason: str


def evaluate_loss_cooldown(
    now: datetime,
    last_stop_time: datetime | None,
    cooldown_minutes: int = 60,
) -> CooldownDecision:
    if last_stop_time is None:
        return CooldownDecision(True, "No active loss cooldown.")

    if now < last_stop_time + timedelta(minutes=cooldown_minutes):
        return CooldownDecision(False, "Loss cooldown is still active.")

    return CooldownDecision(True, "Loss cooldown complete.")
