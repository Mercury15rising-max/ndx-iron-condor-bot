from datetime import date

from liquidity import LiquidityRules, filter_liquid_quotes
from live_market_data import RobinhoodMarketDataProvider
from strategy import build_iron_condor


def scan_live_condor(
    provider: RobinhoodMarketDataProvider,
    chain_symbol: str,
    expiration: date,
    short_delta_min: float,
    short_delta_max: float,
    wing_width: float,
    max_bid_ask_width: float,
    min_bid: float,
):
    """Build one read-only iron-condor candidate from live Robinhood option data."""
    quotes = provider.get_option_chain(chain_symbol, expiration)
    liquid = filter_liquid_quotes(
        quotes,
        LiquidityRules(
            max_bid_ask_width=max_bid_ask_width,
            min_bid=min_bid,
        ),
    )
    if not liquid:
        raise ValueError("No liquid option quotes remained after filtering.")

    return build_iron_condor(
        liquid,
        short_delta_min=short_delta_min,
        short_delta_max=short_delta_max,
        wing_width=wing_width,
    )
