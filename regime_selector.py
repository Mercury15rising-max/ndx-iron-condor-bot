from dataclasses import dataclass
from typing import Literal

Regime = Literal[
    "neutral_high_iv",
    "neutral_tight",
    "moderate_bullish",
    "moderate_bearish",
    "strong_bullish",
    "strong_bearish",
    "event_term_structure",
    "no_trade",
]


@dataclass(frozen=True)
class RegimeInputs:
    directional_score: float
    volatility_score: float
    event_risk: bool = False
    term_structure_signal: bool = False
    confidence: float = 1.0


@dataclass(frozen=True)
class RegimeDecision:
    regime: Regime
    preferred_strategy: str
    reason: str


def classify_regime(inputs: RegimeInputs) -> RegimeDecision:
    if inputs.confidence < 0.50:
        return RegimeDecision("no_trade", "none", "Research confidence below 0.50.")

    if inputs.event_risk:
        if inputs.term_structure_signal:
            return RegimeDecision(
                "event_term_structure",
                "calendar_spread",
                "Event risk present with a term-structure signal.",
            )
        return RegimeDecision("no_trade", "none", "Event risk present without a validated event strategy.")

    d = inputs.directional_score
    v = inputs.volatility_score

    if abs(d) < 0.20:
        if v >= 0.60:
            return RegimeDecision("neutral_high_iv", "iron_condor", "Neutral direction with elevated volatility.")
        return RegimeDecision("neutral_tight", "iron_butterfly", "Neutral direction with contained volatility.")

    if 0.20 <= d < 0.60:
        return RegimeDecision("moderate_bullish", "bull_put_credit_spread", "Moderate bullish research consensus.")
    if -0.60 < d <= -0.20:
        return RegimeDecision("moderate_bearish", "bear_call_credit_spread", "Moderate bearish research consensus.")
    if d >= 0.60:
        return RegimeDecision("strong_bullish", "bull_call_debit_spread", "Strong bullish research consensus.")
    return RegimeDecision("strong_bearish", "bear_put_debit_spread", "Strong bearish research consensus.")
