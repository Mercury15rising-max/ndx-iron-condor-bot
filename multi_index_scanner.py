from dataclasses import dataclass
from datetime import date

from index_watchlist import DEFAULT_INDEX_WATCHLIST, IndexMarket, risk_limit_for_market
from liquidity import LiquidityRules, filter_liquid_quotes
from live_market_data import RobinhoodMarketDataProvider
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
) -> list[MarketSelection]:
    """Read-only multi-index scan. Does not review, place, cancel, or modify orders."""
    results: list[MarketSelection] = []

    for market in DEFAULT_INDEX_WATCHLIST:
        expiration = expirations.get(market.chain_symbol)
        if expiration is None:
            continue

        quotes = provider.get_option_chain(market.chain_symbol, expiration)
        liquid = filter_liquid_quotes(
            quotes,
            LiquidityRules(
                max_bid_ask_width=max_bid_ask_width,
                min_bid=min_bid,
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
        if selection is not None:
            results.append(MarketSelection(market, selection))

    return sorted(results, key=lambda item: item.selection.score, reverse=True)


def best_market_selection_or_none(**kwargs):
    results = scan_index_watchlist(**kwargs)
    return results[0] if results else None
