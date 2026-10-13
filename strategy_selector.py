from dataclasses import dataclass

from butterfly_strategy import build_iron_butterfly
from candidate_scanner import scan_candidates
from models import IronButterfly, OptionQuote, VerticalSpread
from regime_selector import RegimeDecision
from vertical_strategy import build_credit_spread, build_debit_spread


@dataclass(frozen=True)
class StrategySelection:
    strategy: str
    score: float
    payload: object
    reason: str


def _reward_to_risk(max_profit: float, max_loss: float) -> float:
    if max_loss <= 0:
        return 0.0
    return round(max_profit / max_loss, 6)


def _butterfly_score(b: IronButterfly) -> float:
    return _reward_to_risk(b.max_profit, b.max_loss)


def _vertical_selection(
    spread: VerticalSpread,
    strategy: str,
    max_risk_per_trade: float,
    regime_reason: str,
) -> StrategySelection | None:
    if spread.max_loss <= 0 or spread.max_loss > max_risk_per_trade:
        return None
    return StrategySelection(
        strategy=strategy,
        score=_reward_to_risk(spread.max_profit, spread.max_loss),
        payload=spread,
        reason=regime_reason,
    )


def select_strategy_for_regime(
    quotes: list[OptionQuote],
    regime: RegimeDecision,
    *,
    max_risk_per_trade: float,
    max_daily_loss: float,
    condor_wing_widths: list[float] | None = None,
    condor_delta_ranges: list[tuple[float, float]] | None = None,
    butterfly_centers: list[float] | None = None,
    butterfly_wing_widths: list[float] | None = None,
    vertical_wing_width: float = 10.0,
    credit_short_delta: float = 0.20,
    debit_long_delta: float = 0.55,
) -> StrategySelection | None:
    """Build only the strategy family selected by the market-regime engine.

    Calendar spreads remain intentionally disabled until their multi-expiration
    pricing and term-structure validation are implemented.
    """
    if regime.preferred_strategy == "none":
        return None

    if regime.preferred_strategy == "calendar_spread":
        return None

    if regime.preferred_strategy == "iron_condor":
        condors = scan_candidates(
            quotes=quotes,
            wing_widths=condor_wing_widths or [25.0],
            delta_ranges=condor_delta_ranges or [(0.10, 0.15)],
            max_risk_per_trade=max_risk_per_trade,
            max_daily_loss=max_daily_loss,
        )
        if not condors:
            return None
        best = condors[0]
        return StrategySelection(
            strategy="iron_condor",
            score=best.score,
            payload=best.condor,
            reason=regime.reason,
        )

    if regime.preferred_strategy == "iron_butterfly":
        choices: list[StrategySelection] = []
        for center in butterfly_centers or []:
            for width in butterfly_wing_widths or [25.0]:
                try:
                    butterfly = build_iron_butterfly(
                        quotes,
                        center_strike=center,
                        wing_width=width,
                    )
                except ValueError:
                    continue
                if butterfly.max_loss <= 0 or butterfly.max_loss > max_risk_per_trade:
                    continue
                choices.append(
                    StrategySelection(
                        strategy="iron_butterfly",
                        score=_butterfly_score(butterfly),
                        payload=butterfly,
                        reason=regime.reason,
                    )
                )
        return max(choices, key=lambda item: item.score) if choices else None

    try:
        if regime.preferred_strategy == "bull_put_credit_spread":
            spread = build_credit_spread(
                quotes,
                bullish=True,
                short_delta=credit_short_delta,
                wing_width=vertical_wing_width,
            )
        elif regime.preferred_strategy == "bear_call_credit_spread":
            spread = build_credit_spread(
                quotes,
                bullish=False,
                short_delta=credit_short_delta,
                wing_width=vertical_wing_width,
            )
        elif regime.preferred_strategy == "bull_call_debit_spread":
            spread = build_debit_spread(
                quotes,
                bullish=True,
                long_delta=debit_long_delta,
                wing_width=vertical_wing_width,
            )
        elif regime.preferred_strategy == "bear_put_debit_spread":
            spread = build_debit_spread(
                quotes,
                bullish=False,
                long_delta=debit_long_delta,
                wing_width=vertical_wing_width,
            )
        else:
            return None
    except ValueError:
        return None

    return _vertical_selection(
        spread,
        regime.preferred_strategy,
        max_risk_per_trade,
        regime.reason,
    )


def select_best_strategy(
    quotes: list[OptionQuote],
    condor_wing_widths: list[float],
    condor_delta_ranges: list[tuple[float, float]],
    butterfly_centers: list[float],
    butterfly_wing_widths: list[float],
    max_risk_per_trade: float,
    max_daily_loss: float,
) -> StrategySelection | None:
    """Legacy neutral selector retained for backwards compatibility."""
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

    return max(choices, key=lambda item: item.score) if choices else None
