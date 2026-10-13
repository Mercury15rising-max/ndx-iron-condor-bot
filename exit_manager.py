from dataclasses import dataclass
from typing import Literal

ExitAction = Literal["hold", "take_profit", "stop_loss", "time_exit", "kill_switch"]


@dataclass(frozen=True)
class ExitDecision:
    action: ExitAction
    reason: str


def evaluate_exit(
    entry_credit: float,
    current_debit_to_close: float,
    profit_target_pct: float,
    stop_loss_multiple: float,
    minutes_to_close: int | None = None,
    time_exit_minutes: int | None = None,
    daily_realized_pnl: float = 0.0,
    max_daily_loss: float | None = None,
) -> ExitDecision:
    """Pure decision logic only; never places or modifies an order."""
    if entry_credit <= 0:
        raise ValueError("entry_credit must be positive.")
    if current_debit_to_close < 0:
        raise ValueError("current_debit_to_close cannot be negative.")

    if max_daily_loss is not None and daily_realized_pnl <= -abs(max_daily_loss):
        return ExitDecision("kill_switch", "Daily loss limit reached.")

    profit_target_debit = entry_credit * (1 - profit_target_pct / 100)
    if current_debit_to_close <= profit_target_debit:
        return ExitDecision(
            "take_profit",
            f"Debit to close {current_debit_to_close:.2f} reached profit target "
            f"{profit_target_debit:.2f}.",
        )

    stop_debit = entry_credit * stop_loss_multiple
    if current_debit_to_close >= stop_debit:
        return ExitDecision(
            "stop_loss",
            f"Debit to close {current_debit_to_close:.2f} reached stop threshold "
            f"{stop_debit:.2f}.",
        )

    if (
        time_exit_minutes is not None
        and minutes_to_close is not None
        and minutes_to_close <= time_exit_minutes
    ):
        return ExitDecision(
            "time_exit",
            f"{minutes_to_close} minutes remain; time exit threshold is "
            f"{time_exit_minutes} minutes.",
        )

    return ExitDecision("hold", "No exit rule triggered.")
