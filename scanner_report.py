from candidate_scanner import RankedCandidate


def format_candidate(candidate: RankedCandidate | None) -> str:
    if candidate is None:
        return "NO TRADE — no candidate passed all configured rules."

    c = candidate.condor
    return (
        f"APPROVED CANDIDATE\n"
        f"Expiration: {c.expiration}\n"
        f"Legs: {c.long_put.strike}P / {c.short_put.strike}P / "
        f"{c.short_call.strike}C / {c.long_call.strike}C\n"
        f"Net credit: {c.net_credit:.2f}\n"
        f"Max profit: ${c.max_profit:.2f}\n"
        f"Max loss: ${c.max_loss:.2f}\n"
        f"Breakevens: {c.lower_breakeven:.2f} to {c.upper_breakeven:.2f}\n"
        f"Score: {candidate.score:.4f}\n"
        f"Risk: {candidate.risk_reason}"
    )
