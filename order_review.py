from dataclasses import asdict
from models import IronCondor
from robinhood_mcp_tools import RobinhoodTradingMCP


def build_review_payload(condor: IronCondor, quantity: int = 1) -> dict:
    if quantity < 1:
        raise ValueError("quantity must be at least 1")

    return {
        "strategy": "iron_condor",
        "symbol": condor.short_put.symbol,
        "expiration": condor.expiration.isoformat(),
        "quantity": quantity,
        "order_type": "limit",
        "price_effect": "credit",
        "limit_price": condor.net_credit,
        "legs": [
            {
                "position_effect": "open",
                "side": "buy",
                "option_type": "put",
                "strike": condor.long_put.strike,
            },
            {
                "position_effect": "open",
                "side": "sell",
                "option_type": "put",
                "strike": condor.short_put.strike,
            },
            {
                "position_effect": "open",
                "side": "sell",
                "option_type": "call",
                "strike": condor.short_call.strike,
            },
            {
                "position_effect": "open",
                "side": "buy",
                "option_type": "call",
                "strike": condor.long_call.strike,
            },
        ],
        "risk_summary": {
            "max_profit": condor.max_profit * quantity,
            "max_loss": condor.max_loss * quantity,
            "lower_breakeven": condor.lower_breakeven,
            "upper_breakeven": condor.upper_breakeven,
        },
    }


def review_with_robinhood(
    client: RobinhoodTradingMCP,
    condor: IronCondor,
    quantity: int = 1,
) -> dict:
    payload = build_review_payload(condor, quantity)
    return client.review_option_order(payload)
