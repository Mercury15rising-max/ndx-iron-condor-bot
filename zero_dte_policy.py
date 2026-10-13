from dataclasses import dataclass


@dataclass(frozen=True)
class ZeroDTEPolicy:
    enabled: bool = False
    paper_only: bool = True
    allowed_chain_symbols: tuple[str, ...] = ("SPXW",)
    max_risk_per_trade: float = 250.0
    max_trades_per_day: int = 1
    max_open_positions: int = 1
    max_bid_ask_width: float = 1.50
    min_bid: float = 0.10
    profit_target_pct: float = 40.0
    stop_loss_multiple: float = 1.5
    time_exit_minutes: int = 60


DEFAULT_ZERO_DTE_POLICY = ZeroDTEPolicy()


def validate_zero_dte_request(
    *,
    chain_symbol: str,
    trading_mode: str,
    live_orders_enabled: bool,
    policy: ZeroDTEPolicy = DEFAULT_ZERO_DTE_POLICY,
) -> tuple[bool, str]:
    if not policy.enabled:
        return False, "0DTE strategy is disabled."

    if chain_symbol not in policy.allowed_chain_symbols:
        return False, f"0DTE is not enabled for {chain_symbol}."

    if policy.paper_only and trading_mode != "paper":
        return False, "0DTE is restricted to paper mode."

    if policy.paper_only and live_orders_enabled:
        return False, "0DTE live order placement is disabled."

    return True, "0DTE policy checks passed."
