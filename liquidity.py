from dataclasses import dataclass
from models import OptionQuote

@dataclass(frozen=True)
class LiquidityRules:
    max_bid_ask_width: float = 2.50
    min_bid: float = 0.10

def is_liquid(quote: OptionQuote, rules: LiquidityRules) -> bool:
    width = quote.ask - quote.bid
    return quote.bid >= rules.min_bid and width <= rules.max_bid_ask_width

def filter_liquid_quotes(
    quotes: list[OptionQuote],
    rules: LiquidityRules,
) -> list[OptionQuote]:
    return [q for q in quotes if is_liquid(q, rules)]
