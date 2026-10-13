from dataclasses import dataclass
from typing import Any

from models import IronButterfly, IronCondor, VerticalSpread
from strategy_selector import StrategySelection


@dataclass(frozen=True)
class PaperExecutionPlan:
    strategy: str
    chain_symbol: str
    expiration: str
    max_profit: float
    max_loss: float
    score: float
    legs: tuple[dict[str, Any], ...]
    reason: str


def build_paper_execution_plan(selection: StrategySelection) -> PaperExecutionPlan:
    payload = selection.payload

    if isinstance(payload, IronCondor):
        legs = (
            {"side": "buy", "option_type": "put", "strike": payload.long_put.strike},
            {"side": "sell", "option_type": "put", "strike": payload.short_put.strike},
            {"side": "sell", "option_type": "call", "strike": payload.short_call.strike},
            {"side": "buy", "option_type": "call", "strike": payload.long_call.strike},
        )
        symbol = payload.short_put.symbol
        expiration = payload.expiration.isoformat()
    elif isinstance(payload, IronButterfly):
        legs = (
            {"side": "buy", "option_type": "put", "strike": payload.long_put.strike},
            {"side": "sell", "option_type": "put", "strike": payload.short_put.strike},
            {"side": "sell", "option_type": "call", "strike": payload.short_call.strike},
            {"side": "buy", "option_type": "call", "strike": payload.long_call.strike},
        )
        symbol = payload.short_put.symbol
        expiration = payload.expiration.isoformat()
    elif isinstance(payload, VerticalSpread):
        legs = (
            {
                "side": "buy",
                "option_type": payload.long_option.option_type,
                "strike": payload.long_option.strike,
            },
            {
                "side": "sell",
                "option_type": payload.short_option.option_type,
                "strike": payload.short_option.strike,
            },
        )
        symbol = payload.long_option.symbol
        expiration = payload.expiration.isoformat()
    else:
        raise TypeError("Unsupported strategy payload.")

    return PaperExecutionPlan(
        strategy=selection.strategy,
        chain_symbol=symbol,
        expiration=expiration,
        max_profit=payload.max_profit,
        max_loss=payload.max_loss,
        score=selection.score,
        legs=legs,
        reason=selection.reason,
    )
