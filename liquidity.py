from dataclasses import dataclass
from models import OptionQuote


@dataclass(frozen=True)
class LiquidityRules:
    max_bid_ask_width: float = 2.50
    max_bid_ask_pct: float | None = 0.20
    min_bid: float = 0.10
    min_open_interest: int = 0
    min_volume: int = 0


def is_liquid(quote: OptionQuote, rules: LiquidityRules) -> bool:
    width = quote.ask - quote.bid
    if quote.bid < rules.min_bid or width > rules.max_bid_ask_width:
        return False

    if rules.max_bid_ask_pct is not None:
        mid = quote.mid
        if mid <= 0 or width / mid > rules.max_bid_ask_pct:
            return False

    if quote.open_interest is not None and quote.open_interest < rules.min_open_interest:
        return False

    if quote.volume is not None and quote.volume < rules.min_volume:
        return False

    return True


def filter_liquid_quotes(
    quotes: list[OptionQuote],
    rules: LiquidityRules,
) -> list[OptionQuote]:
    return [q for q in quotes if is_liquid(q, rules)]
