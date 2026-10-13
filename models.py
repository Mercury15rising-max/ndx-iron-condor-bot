from dataclasses import dataclass
from datetime import date
from typing import Literal

OptionType = Literal["call", "put"]

@dataclass(frozen=True)
class OptionQuote:
    symbol: str
    expiration: date
    strike: float
    option_type: OptionType
    bid: float
    ask: float
    delta: float

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2, 2)

@dataclass(frozen=True)
class IronCondor:
    expiration: date
    long_put: OptionQuote
    short_put: OptionQuote
    short_call: OptionQuote
    long_call: OptionQuote
    net_credit: float
    max_profit: float
    max_loss: float
    lower_breakeven: float
    upper_breakeven: float


@dataclass(frozen=True)
class IronButterfly:
    expiration: date
    long_put: OptionQuote
    short_put: OptionQuote
    short_call: OptionQuote
    long_call: OptionQuote
    net_credit: float
    max_profit: float
    max_loss: float
    lower_breakeven: float
    upper_breakeven: float
