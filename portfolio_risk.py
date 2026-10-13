from dataclasses import dataclass


CORRELATION_FAMILY = {
    "NDX": "tech_index",
    "NDXP": "tech_index",
    "SOXX": "tech_index",
    "QQQ": "tech_index",
    "SPX": "broad_index",
    "SPXW": "broad_index",
    "XSP": "broad_index",
    "SPXL": "broad_index",
}


@dataclass(frozen=True)
class PortfolioRiskDecision:
    approved: bool
    reason: str


def evaluate_portfolio_risk(
    *,
    candidate_symbol: str,
    candidate_max_loss: float,
    total_open_risk: float,
    max_total_open_risk: float,
    open_symbols: list[str],
    max_positions_per_family: int = 1,
) -> PortfolioRiskDecision:
    if total_open_risk + candidate_max_loss > max_total_open_risk:
        return PortfolioRiskDecision(False, "Maximum total portfolio risk exceeded.")

    family = CORRELATION_FAMILY.get(candidate_symbol, candidate_symbol)
    family_count = sum(
        1 for symbol in open_symbols
        if CORRELATION_FAMILY.get(symbol, symbol) == family
    )
    if family_count >= max_positions_per_family:
        return PortfolioRiskDecision(
            False,
            f"Correlation-family exposure limit reached for {family}.",
        )

    return PortfolioRiskDecision(True, "Portfolio risk checks passed.")
