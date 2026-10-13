from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateQualityRules:
    min_return_on_risk: float = 0.10
    min_credit_to_width: float = 0.10


@dataclass(frozen=True)
class CandidateQualityDecision:
    approved: bool
    reason: str


def evaluate_candidate_quality(
    trade: Any,
    rules: CandidateQualityRules,
) -> CandidateQualityDecision:
    if trade.max_loss <= 0 or trade.max_profit <= 0:
        return CandidateQualityDecision(False, "Trade has invalid risk/reward.")

    return_on_risk = trade.max_profit / trade.max_loss

    put_width = trade.short_put.strike - trade.long_put.strike
    call_width = trade.long_call.strike - trade.short_call.strike
    widest_width = max(put_width, call_width)
    if widest_width <= 0:
        return CandidateQualityDecision(False, "Trade has invalid wing width.")

    credit_to_width = trade.net_credit / widest_width

    if return_on_risk < rules.min_return_on_risk:
        return CandidateQualityDecision(
            False,
            f"Return on risk {return_on_risk:.3f} below minimum "
            f"{rules.min_return_on_risk:.3f}.",
        )

    if credit_to_width < rules.min_credit_to_width:
        return CandidateQualityDecision(
            False,
            f"Credit/width {credit_to_width:.3f} below minimum "
            f"{rules.min_credit_to_width:.3f}.",
        )

    return CandidateQualityDecision(True, "Candidate quality checks passed.")
