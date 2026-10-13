from dataclasses import dataclass
from datetime import date, datetime

from candidate_quality import CandidateQualityRules, evaluate_candidate_quality
from cooldown import evaluate_loss_cooldown
from event_filter import ScheduledEvent, evaluate_event_risk
from index_watchlist import DEFAULT_INDEX_WATCHLIST, IndexMarket, risk_limit_for_market
from liquidity import LiquidityRules, filter_liquid_quotes
from live_market_data import RobinhoodMarketDataProvider
from portfolio_risk import evaluate_portfolio_risk
from strategy_selector import StrategySelection, select_best_strategy


@dataclass(frozen=True)
class MarketSelection:
    market: IndexMarket
    selection: StrategySelection


def scan_index_watchlist(
    provider: RobinhoodMarketDataProvider,
    expirations: dict[str, date],
    base_max_risk_per_trade: float,
    max_daily_loss: float,
    condor_wing_widths: list[float],
    condor_delta_ranges: list[tuple[float, float]],
    butterfly_wing_widths: list[float],
    butterfly_centers: dict[str, list[float]],
    max_bid_ask_width: float,
    min_bid: float,
    *,
    max_bid_ask_pct: float | None = 0.20,
    min_open_interest: int = 0,
    min_volume: int = 0,
    min_return_on_risk: float = 0.10,
    min_credit_to_width: float = 0.10,
    now: datetime | None = None,
    scheduled_events: list[ScheduledEvent] | None = None,
    event_block_before_minutes: int = 45,
    event_block_after_minutes: int = 30,
    total_open_risk: float = 0.0,
    max_total_open_risk: float = 750.0,
    open_symbols: list[str] | None = None,
    max_positions_per_family: int = 1,
    last_stop_time: datetime | None = None,
    loss_cooldown_minutes: int = 60,
) -> list[MarketSelection]:
    """Read-only hardened multi-index scan.

    Applies event, cooldown, liquidity, candidate-quality, and portfolio-risk
    gates. It never reviews, places, cancels, or modifies orders.
    """
    results: list[MarketSelection] = []
    open_symbols = open_symbols or []
    scheduled_events = scheduled_events or []

    if now is not None:
        cooldown = evaluate_loss_cooldown(
            now=now,
            last_stop_time=last_stop_time,
            cooldown_minutes=loss_cooldown_minutes,
        )
        if not cooldown.allow_entry:
            return []

        event_decision = evaluate_event_risk(
            now=now,
            events=scheduled_events,
            block_before_minutes=event_block_before_minutes,
            block_after_minutes=event_block_after_minutes,
        )
        if not event_decision.allow_entry:
            return []

    quality_rules = CandidateQualityRules(
        min_return_on_risk=min_return_on_risk,
        min_credit_to_width=min_credit_to_width,
    )

    for market in DEFAULT_INDEX_WATCHLIST:
        expiration = expirations.get(market.chain_symbol)
        if expiration is None:
            continue

        quotes = provider.get_option_chain(market.chain_symbol, expiration)
        liquid = filter_liquid_quotes(
            quotes,
            LiquidityRules(
                max_bid_ask_width=max_bid_ask_width,
                max_bid_ask_pct=max_bid_ask_pct,
                min_bid=min_bid,
                min_open_interest=min_open_interest,
                min_volume=min_volume,
            ),
        )
        if not liquid:
            continue

        selection = select_best_strategy(
            quotes=liquid,
            condor_wing_widths=condor_wing_widths,
            condor_delta_ranges=condor_delta_ranges,
            butterfly_centers=butterfly_centers.get(market.chain_symbol, []),
            butterfly_wing_widths=butterfly_wing_widths,
            max_risk_per_trade=risk_limit_for_market(
                base_max_risk_per_trade, market
            ),
            max_daily_loss=max_daily_loss,
        )
        if selection is None:
            continue

        quality = evaluate_candidate_quality(selection.payload, quality_rules)
        if not quality.approved:
            continue

        portfolio = evaluate_portfolio_risk(
            candidate_symbol=market.chain_symbol,
            candidate_max_loss=selection.payload.max_loss,
            total_open_risk=total_open_risk,
            max_total_open_risk=max_total_open_risk,
            open_symbols=open_symbols,
            max_positions_per_family=max_positions_per_family,
        )
        if not portfolio.approved:
            continue

        results.append(MarketSelection(market, selection))

    return sorted(results, key=lambda item: item.selection.score, reverse=True)


def best_market_selection_or_none(**kwargs):
    results = scan_index_watchlist(**kwargs)
    return results[0] if results else None
