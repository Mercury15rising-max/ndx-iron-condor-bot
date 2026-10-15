from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

GateAction = Literal["allow", "reject", "kill_switch"]


@dataclass(frozen=True)
class SafetyDecision:
    action: GateAction
    reason: str


def evaluate_entry_safety(
    *,
    quote_timestamp: datetime | None,
    now: datetime | None = None,
    max_quote_age_seconds: int = 30,
    daily_realized_pnl: float = 0.0,
    max_daily_loss: float = 75.0,
    open_positions: int = 0,
    max_open_positions: int = 1,
    trades_today: int = 0,
    max_trades_per_day: int = 1,
    consecutive_losses: int = 0,
    max_consecutive_losses: int = 2,
) -> SafetyDecision:
    """Central entry gate. Pure logic only; never sends orders."""
    if daily_realized_pnl <= -abs(max_daily_loss):
        return SafetyDecision("kill_switch", "Daily loss limit reached.")

    if consecutive_losses >= max_consecutive_losses:
        return SafetyDecision(
            "kill_switch",
            "Maximum consecutive-loss threshold reached.",
        )

    if open_positions >= max_open_positions:
        return SafetyDecision("reject", "Maximum open positions reached.")

    if trades_today >= max_trades_per_day:
        return SafetyDecision("reject", "Maximum trades per day reached.")

    if quote_timestamp is None:
        return SafetyDecision("reject", "Missing quote timestamp.")

    if now is None:
        now = datetime.now(timezone.utc)

    if (quote_timestamp.tzinfo is None or quote_timestamp.utcoffset() is None
            or now.tzinfo is None or now.utcoffset() is None):
        return SafetyDecision("reject", "Timezone-aware quote and observation timestamps required.")

    age = (now - quote_timestamp.astimezone(timezone.utc)).total_seconds()
    if age < 0:
        return SafetyDecision("reject", "Quote timestamp is in the future.")
    if age > max_quote_age_seconds:
        return SafetyDecision(
            "reject",
            f"Quote is stale ({age:.0f}s old; limit {max_quote_age_seconds}s).",
        )

    return SafetyDecision("allow", "Entry safety checks passed.")

