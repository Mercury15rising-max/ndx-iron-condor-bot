from datetime import date, timedelta

def choose_expiration(
    today: date,
    available_expirations: list[date],
    allow_0dte: bool,
    min_dte: int = 1,
    max_dte: int = 7,
) -> date:
    """Choose the nearest eligible expiration inside the configured DTE window."""
    eligible = []
    for expiration in available_expirations:
        dte = (expiration - today).days
        if dte < 0:
            continue
        if dte == 0 and not allow_0dte:
            continue
        if dte < min_dte or dte > max_dte:
            continue
        eligible.append(expiration)

    if not eligible:
        raise ValueError("No eligible expiration found in configured DTE window.")

    return min(eligible)
