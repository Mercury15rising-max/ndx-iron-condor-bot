"""Shared conservative research limits; these do not authorize live orders."""
from decimal import Decimal

STARTING_BALANCE = Decimal('3000')
MAX_TRADE_RISK = Decimal('30')
MAX_DAILY_LOSS = Decimal('60')

def risk_limits(balance):
    balance = Decimal(str(balance))
    if not balance.is_finite() or balance <= 0:
        raise ValueError('invalid balance')
    return min(MAX_TRADE_RISK, balance * Decimal('.01')), min(MAX_DAILY_LOSS, balance * Decimal('.02'))
