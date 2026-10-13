from models import IronCondor

class RobinhoodMCPBroker:
    """Adapter boundary for Robinhood Trading MCP.

    Version 1 intentionally does not submit live orders.
    It converts an approved condor into a reviewable order payload.
    """

    def __init__(self, live_orders_enabled: bool = False):
        self.live_orders_enabled = live_orders_enabled

    def preview_order(self, condor: IronCondor) -> dict:
        return {
            "strategy": "iron_condor",
            "expiration": condor.expiration.isoformat(),
            "legs": [
                {"action": "buy", "type": "put", "strike": condor.long_put.strike},
                {"action": "sell", "type": "put", "strike": condor.short_put.strike},
                {"action": "sell", "type": "call", "strike": condor.short_call.strike},
                {"action": "buy", "type": "call", "strike": condor.long_call.strike},
            ],
            "net_credit": condor.net_credit,
            "max_profit": condor.max_profit,
            "max_loss": condor.max_loss,
            "lower_breakeven": condor.lower_breakeven,
            "upper_breakeven": condor.upper_breakeven,
            "mode": "live" if self.live_orders_enabled else "paper",
        }

    def submit_order(self, condor: IronCondor) -> dict:
        if not self.live_orders_enabled:
            raise RuntimeError("Live Robinhood order submission is disabled.")
        raise NotImplementedError(
            "Live MCP submission will be implemented only after the exact Robinhood MCP "
            "multi-leg options schema is verified."
        )
