"""Small-account credit-spread paper risk gate; never submits orders."""
from dataclasses import dataclass
from decimal import Decimal as D

@dataclass(frozen=True)
class PaperAccount:
    balance: D = D("3000")
    daily_loss: D = D("0")
    open_risk: D = D("0")
    open_positions: int = 0
    trades_today: int = 0

def assess_spread(*, width, short_bid, long_ask, account=PaperAccount(),
                  fee_per_contract="1", slippage_per_leg="0.01",
                  data_checks_passed=False, signal_passed=False):
    """One standard 100-multiplier credit spread; caller supplies validated legs.
    Missing data/signal gates fail closed. Costs are assumptions, not broker fees.
    Assesses risk only: symbol, expiry, direction, liquidity, freshness, events,
    and session checks must be validated upstream.
    """
    w, bid, ask, fee, slip = map(lambda v: D(str(v)),
                                [width, short_bid, long_ask, fee_per_contract, slippage_per_leg])
    if any(not x.is_finite() for x in [w,bid,ask,fee,slip,account.balance,account.daily_loss,account.open_risk]):
        raise ValueError("nonfinite input")
    if w <= 0 or min(bid,ask,fee,slip,account.daily_loss,account.open_risk) < 0 or account.balance <= 0:
        raise ValueError("invalid price, cost or account")
    if account.open_positions < 0 or account.trades_today < 0:
        raise ValueError("invalid counters")
    credit = bid - ask - 2 * slip
    costs = 4 * fee
    risk = (w - credit) * 100 + costs
    # Fixed ceilings intentionally remain unchanged when starting capital increases.
    cap = min(D("5"), account.balance * D(".02"))
    daily_cap = min(D("10"), account.balance * D(".04"))
    # Buyback at 75% of entry credit targets 25% gross credit capture.
    target_debit = credit * D(".75")
    target_net = (credit-target_debit-2*slip)*100-costs
    reasons = []
    if not D("0") < credit < w:
        reasons.append("invalid_credit")
    if risk <= 0 or risk > cap:
        reasons.append("per_trade_risk")
    if account.open_risk + max(risk,D("0")) > cap:
        reasons.append("total_open_risk")
    if account.daily_loss + account.open_risk + max(risk,D("0")) > daily_cap:
        reasons.append("daily_loss_budget")
    if account.open_positions >= 1 or account.trades_today >= 1:
        reasons.append("position_or_trade_limit")
    if target_net < D("1"):
        reasons.append("target_consumed_by_costs")
    if not data_checks_passed:
        reasons.append("data_gates_not_verified")
    if not signal_passed:
        reasons.append("directional_signal_not_verified")
    return {
        "mode":"paper", "filled":False,
        "status":"rejected" if reasons else "paper_candidate",
        "reasons":reasons, "paper_balance":str(account.balance),
        "risk_cap":str(cap), "daily_loss_cap":str(daily_cap),
        "entry_credit_points":str(credit), "max_loss_with_reserved_fees":str(risk),
        "target_buyback_points":str(target_debit),
        "target_net_after_assumed_costs":str(target_net),
        "profit_guaranteed":False
    }
