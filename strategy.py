from typing import Iterable
from models import OptionQuote, IronCondor

CONTRACT_MULTIPLIER = 100

def _nearest_by_strike(options: Iterable[OptionQuote], target: float) -> OptionQuote:
    candidates = list(options)
    if not candidates:
        raise ValueError("No protective wing candidates available.")
    return min(candidates, key=lambda q: abs(q.strike - target))

def build_iron_condor(
    quotes: list[OptionQuote],
    short_delta_min: float,
    short_delta_max: float,
    wing_width: float,
) -> IronCondor:
    puts = [q for q in quotes if q.option_type == "put"]
    calls = [q for q in quotes if q.option_type == "call"]
    if not puts or not calls:
        raise ValueError("Option chain must contain both puts and calls.")

    short_put_candidates = [
        q for q in puts if short_delta_min <= abs(q.delta) <= short_delta_max
    ]
    short_call_candidates = [
        q for q in calls if short_delta_min <= abs(q.delta) <= short_delta_max
    ]
    if not short_put_candidates or not short_call_candidates:
        raise ValueError("No short-strike candidates matched the configured delta range.")

    short_put = max(short_put_candidates, key=lambda q: q.strike)
    short_call = min(short_call_candidates, key=lambda q: q.strike)

    long_put = _nearest_by_strike(
        [q for q in puts if q.strike < short_put.strike],
        short_put.strike - wing_width,
    )
    long_call = _nearest_by_strike(
        [q for q in calls if q.strike > short_call.strike],
        short_call.strike + wing_width,
    )

    credit = round(
        (short_put.mid - long_put.mid) + (short_call.mid - long_call.mid), 2
    )
    if credit <= 0:
        raise ValueError("Candidate iron condor does not produce a positive net credit.")

    put_width = short_put.strike - long_put.strike
    call_width = long_call.strike - short_call.strike
    widest = max(put_width, call_width)

    max_profit = round(credit * CONTRACT_MULTIPLIER, 2)
    max_loss = round((widest - credit) * CONTRACT_MULTIPLIER, 2)

    return IronCondor(
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
