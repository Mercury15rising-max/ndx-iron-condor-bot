from dataclasses import dataclass
from models import IronCondor

@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str

def evaluate_trade(
    condor: IronCondor,
    max_risk_per_trade: float,
    daily_realized_pnl: float,
    max_daily_loss: float,
    open_positions: int,
    max_open_positions: int,
    trades_today: int,
    max_trades_per_day: int,
) -> RiskDecision:
    if daily_realized_pnl <= -abs(max_daily_loss):
        return RiskDecision(False, "Daily loss limit reached.")
    if open_positions >= max_open_positions:
        return RiskDecision(False, "Maximum open positions reached.")
    if trades_today >= max_trades_per_day:
        return RiskDecision(False, "Maximum trades per day reached.")
    if condor.max_loss > max_risk_per_trade:
        return RiskDecision(
            False,
            f"Max loss {condor.max_loss:.2f} exceeds per-trade limit {max_risk_per_trade:.2f}.",
        )
    return RiskDecision(True, "Trade passed configured risk checks.")
