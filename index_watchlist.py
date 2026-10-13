from dataclasses import dataclass


@dataclass(frozen=True)
class IndexMarket:
    underlying_symbol: str
    chain_symbol: str
    settlement: str
    risk_multiplier: float = 1.0


DEFAULT_INDEX_WATCHLIST = (
    IndexMarket("NDX", "NDXP", "PM", 1.0),
    IndexMarket("NDX", "NDX", "AM", 1.0),
    IndexMarket("SPX", "SPXW", "PM", 1.0),
    IndexMarket("SPX", "SPX", "AM", 1.0),
    IndexMarket("XSP", "XSP", "PM", 0.5),
)


def risk_limit_for_market(base_max_risk: float, market: IndexMarket) -> float:
    return round(base_max_risk * market.risk_multiplier, 2)
