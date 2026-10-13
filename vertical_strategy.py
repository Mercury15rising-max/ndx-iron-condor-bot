from dataclasses import dataclass

from models import OptionQuote, VerticalSpread


def _nearest_by_abs_delta(quotes: list[OptionQuote], target: float) -> OptionQuote:
    if not quotes:
        raise ValueError("No matching option quotes.")
    return min(quotes, key=lambda q: abs(abs(q.delta) - target))


def _nearest_strike(quotes: list[OptionQuote], strike: float) -> OptionQuote:
    if not quotes:
        raise ValueError("No matching protective options.")
    return min(quotes, key=lambda q: abs(q.strike - strike))


def build_credit_spread(
    quotes: list[OptionQuote],
    *,
    bullish: bool,
    short_delta: float = 0.20,
    wing_width: float = 10.0,
) -> VerticalSpread:
    option_type = "put" if bullish else "call"
    side = [q for q in quotes if q.option_type == option_type]
    short = _nearest_by_abs_delta(side, short_delta)

    if bullish:
        protective = [q for q in side if q.strike < short.strike]
        long = _nearest_strike(protective, short.strike - wing_width)
        width = short.strike - long.strike
    else:
        protective = [q for q in side if q.strike > short.strike]
        long = _nearest_strike(protective, short.strike + wing_width)
        width = long.strike - short.strike

    credit = round(short.mid - long.mid, 2)
    if credit <= 0 or width <= 0:
        raise ValueError("Invalid credit spread pricing.")

    return VerticalSpread(
        expiration=short.expiration,
        option_type=option_type,
        direction="bullish" if bullish else "bearish",
        premium_type="credit",
        long_option=long,
        short_option=short,
        net_premium=credit,
        max_profit=round(credit * 100, 2),
        max_loss=round((width - credit) * 100, 2),
    )


def build_debit_spread(
    quotes: list[OptionQuote],
    *,
    bullish: bool,
    long_delta: float = 0.55,
    wing_width: float = 10.0,
) -> VerticalSpread:
    option_type = "call" if bullish else "put"
    side = [q for q in quotes if q.option_type == option_type]
    long = _nearest_by_abs_delta(side, long_delta)

    if bullish:
        shorts = [q for q in side if q.strike > long.strike]
        short = _nearest_strike(shorts, long.strike + wing_width)
        width = short.strike - long.strike
    else:
        shorts = [q for q in side if q.strike < long.strike]
        short = _nearest_strike(shorts, long.strike - wing_width)
        width = long.strike - short.strike

    debit = round(long.mid - short.mid, 2)
    if debit <= 0 or width <= 0:
        raise ValueError("Invalid debit spread pricing.")

    return VerticalSpread(
        expiration=long.expiration,
        option_type=option_type,
        direction="bullish" if bullish else "bearish",
        premium_type="debit",
        long_option=long,
        short_option=short,
        net_premium=debit,
        max_profit=round((width - debit) * 100, 2),
        max_loss=round(debit * 100, 2),
    )
