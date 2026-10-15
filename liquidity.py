from dataclasses import dataclass
from math import isfinite
from models import OptionQuote


@dataclass(frozen=True)
class LiquidityRules:
    max_bid_ask_width: float = 2.50
    max_bid_ask_pct: float | None = 0.20
    min_bid: float = 0.10
    min_open_interest: int = 0
    min_volume: int = 0


def is_liquid(quote: OptionQuote, rules: LiquidityRules) -> bool:
    if (not all(isfinite(v) for v in (quote.bid, quote.ask))
            or quote.bid <= 0 or quote.ask < quote.bid):
        return False
    width = quote.ask - quote.bid
    if quote.bid < rules.min_bid or width > rules.max_bid_ask_width:
        return False

    if rules.max_bid_ask_pct is not None:
        mid = quote.mid
        if mid <= 0 or width / mid > rules.max_bid_ask_pct:
            return False

    for value, minimum in ((quote.open_interest, rules.min_open_interest),
                           (quote.volume, rules.min_volume)):
        if value is None:
            if minimum > 0:
                return False
        elif not isfinite(value) or value < minimum or value < 0:
            return False

    return True


def filter_liquid_quotes(
    quotes: list[OptionQuote],
    rules: LiquidityRules,
) -> list[OptionQuote]:
    return [q for q in quotes if is_liquid(q, rules)]

