from dataclasses import dataclass

from butterfly_strategy import build_iron_butterfly
from candidate_scanner import RankedCandidate, scan_candidates
from models import IronButterfly, OptionQuote


@dataclass(frozen=True)
class StrategySelection:
    strategy: str
    score: float
    payload: object
    reason: str


def _butterfly_score(b: IronButterfly) -> float:
    if b.max_loss <= 0:
        return 0.0
    return round(b.max_profit / b.max_loss, 6)


def select_best_strategy(
    quotes: list[OptionQuote],
    condor_wing_widths: list[float],
    condor_delta_ranges: list[tuple[float, float]],
    butterfly_centers: list[float],
    butterfly_wing_widths: list[float],
    max_risk_per_trade: float,
    max_daily_loss: float,
) -> StrategySelection | None:
    choices: list[StrategySelection] = []

    condors = scan_candidates(
        quotes=quotes,
        wing_widths=condor_wing_widths,
        delta_ranges=condor_delta_ranges,
        max_risk_per_trade=max_risk_per_trade,
        max_daily_loss=max_daily_loss,
    )
    if condors:
        best = condors[0]
        choices.append(
            StrategySelection(
                strategy="iron_condor",
                score=best.score,
                payload=best.condor,
                reason=best.risk_reason,
            )
        )

    for center in butterfly_centers:
        for width in butterfly_wing_widths:
            try:
                butterfly = build_iron_butterfly(
                    quotes,
                    center_strike=center,
                    wing_width=width,
                )
            except ValueError:
                continue

            if butterfly.max_loss > max_risk_per_trade:
                continue

            choices.append(
                StrategySelection(
                    strategy="iron_butterfly",
                    score=_butterfly_score(butterfly),
                    payload=butterfly,
                    reason="Trade passed configured risk checks.",
                )
            )

    if not choices:
        return None

    return max(choices, key=lambda item: item.score)
