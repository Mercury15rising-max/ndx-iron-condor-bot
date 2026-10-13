from models import OptionQuote, IronButterfly

CONTRACT_MULTIPLIER = 100


def _nearest(options: list[OptionQuote], target: float) -> OptionQuote:
    if not options:
        raise ValueError("No matching option candidates available.")
    return min(options, key=lambda q: abs(q.strike - target))


def build_iron_butterfly(
    quotes: list[OptionQuote],
    center_strike: float,
    wing_width: float,
) -> IronButterfly:
    """Build a defined-risk short iron butterfly around one center strike."""
    puts = [q for q in quotes if q.option_type == "put"]
    calls = [q for q in quotes if q.option_type == "call"]
    if not puts or not calls:
        raise ValueError("Option chain must contain both puts and calls.")

    short_put = _nearest(puts, center_strike)
    short_call = _nearest(calls, center_strike)
    if short_put.strike != short_call.strike:
        raise ValueError("Iron butterfly requires short put and short call at the same strike.")

    long_put = _nearest(
        [q for q in puts if q.strike < short_put.strike],
        short_put.strike - wing_width,
    )
    long_call = _nearest(
        [q for q in calls if q.strike > short_call.strike],
        short_call.strike + wing_width,
    )

    credit = round(
        (short_put.mid + short_call.mid) - (long_put.mid + long_call.mid), 2
    )
    if credit <= 0:
        raise ValueError("Candidate iron butterfly does not produce a positive net credit.")

    put_width = short_put.strike - long_put.strike
    call_width = long_call.strike - short_call.strike
    widest = max(put_width, call_width)

    max_profit = round(credit * CONTRACT_MULTIPLIER, 2)
    max_loss = round((widest - credit) * CONTRACT_MULTIPLIER, 2)

    return IronButterfly(
        expiration=short_put.expiration,
        long_put=long_put,
        short_put=short_put,
        short_call=short_call,
        long_call=long_call,
        net_credit=credit,
        max_profit=max_profit,
        max_loss=max_loss,
        lower_breakeven=round(short_put.strike - credit, 2),
        upper_breakeven=round(short_call.strike + credit, 2),
    )
