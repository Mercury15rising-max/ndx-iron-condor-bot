from datetime import date
from typing import Any

from models import OptionQuote
from robinhood_mcp_tools import RobinhoodTradingMCP


class RobinhoodChainService:
    """Build a normalized NDX chain from Robinhood Trading MCP tool results.

    Field extraction is isolated here so Robinhood schema changes do not leak into
    strategy or risk code.
    """

    def __init__(self, client: RobinhoodTradingMCP):
        self.client = client

    @staticmethod
    def _pick(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        raise KeyError(f"Missing required field; tried: {', '.join(keys)}")

    def get_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        instruments = self.client.get_option_instruments(symbol, expiration)
        if not instruments:
            return []

        ids = [
            str(self._pick(row, "id", "instrument_id", "option_id"))
            for row in instruments
        ]
        quote_rows = self.client.get_option_quotes(ids)
        quotes_by_id = {
            str(self._pick(row, "id", "instrument_id", "option_id")): row
            for row in quote_rows
        }

        normalized: list[OptionQuote] = []

        for instrument in instruments:
            instrument_id = str(
                self._pick(instrument, "id", "instrument_id", "option_id")
            )
            quote = quotes_by_id.get(instrument_id)
            if quote is None:
                continue

            option_type = str(
                self._pick(instrument, "option_type", "type", "side")
            ).lower()

            if option_type not in {"call", "put"}:
                continue

            normalized.append(
                OptionQuote(
                    symbol=symbol,
                    expiration=expiration,
                    strike=float(
                        self._pick(instrument, "strike", "strike_price")
                    ),
                    option_type=option_type,
                    bid=float(self._pick(quote, "bid", "bid_price")),
                    ask=float(self._pick(quote, "ask", "ask_price")),
                    delta=float(self._pick(quote, "delta")),
                )
            )

        return normalized
