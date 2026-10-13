from dataclasses import dataclass
from itertools import product

from models import IronCondor, OptionQuote
from strategy import build_iron_condor
from risk_manager import evaluate_trade


@dataclass(frozen=True)
class RankedCandidate:
    condor: IronCondor
    score: float
    risk_reason: str


def _score(condor: IronCondor) -> float:
    if condor.max_loss <= 0:
        return 0.0
    return round(condor.max_profit / condor.max_loss, 6)


def scan_candidates(
    quotes: list[OptionQuote],
    wing_widths: list[float],
    delta_ranges: list[tuple[float, float]],
    max_risk_per_trade: float,
    max_daily_loss: float,
    daily_realized_pnl: float = 0.0,
    open_positions: int = 0,
    max_open_positions: int = 1,
    trades_today: int = 0,
    max_trades_per_day: int = 1,
) -> list[RankedCandidate]:
    seen: set[tuple] = set()
    approved: list[RankedCandidate] = []

    for wing_width, delta_range in product(wing_widths, delta_ranges):
        delta_min, delta_max = delta_range
        try:
            condor = build_iron_condor(
                quotes,
                short_delta_min=delta_min,
                short_delta_max=delta_max,
                wing_width=wing_width,
            )
        except ValueError:
            continue

        key = (
            condor.expiration,
            condor.long_put.strike,
            condor.short_put.strike,
            condor.short_call.strike,
            condor.long_call.strike,
        )
        if key in seen:
            continue
        seen.add(key)

        decision = evaluate_trade(
            condor,
            max_risk_per_trade=max_risk_per_trade,
            daily_realized_pnl=daily_realized_pnl,
            max_daily_loss=max_daily_loss,
            open_positions=open_positions,
            max_open_positions=max_open_positions,
            trades_today=trades_today,
            max_trades_per_day=max_trades_per_day,
        )

        if not decision.approved:
            continue

        approved.append(
            RankedCandidate(
                condor=condor,
                score=_score(condor),
                risk_reason=decision.reason,
            )
        )

    return sorted(approved, key=lambda item: item.score, reverse=True)


def best_candidate_or_none(**kwargs):
    candidates = scan_candidates(**kwargs)
    return candidates[0] if candidates else None
