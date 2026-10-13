from datetime import date
from typing import Protocol, Any

from market_data import MarketDataProvider
from models import OptionQuote


class RobinhoodOptionsClient(Protocol):
    """Bot-facing protocol for the verified Robinhood Trading MCP market-data tools."""

    def get_option_instruments(
        self,
        *,
        chain_symbol: str,
        expiration_dates: str,
        state: str = "active",
        tradability: str = "tradable",
    ) -> dict[str, Any]:
        ...

    def get_option_quotes(self, *, instrument_ids: list[str]) -> dict[str, Any]:
        ...


class RobinhoodMarketDataProvider(MarketDataProvider):
    """Normalize the verified Robinhood Trading MCP response shapes.

    Verified shapes:
    - get_option_instruments -> {"data": {"instruments": [...]}}
    - get_option_quotes -> {"data": {"results": [{"quote": {...}, "close": {...}}, ...]}}

    This adapter is read-only. It never reviews or places orders.
    """

    def __init__(self, client: RobinhoodOptionsClient):
        self.client = client

    def get_option_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        instrument_response = self.client.get_option_instruments(
            chain_symbol=symbol,
            expiration_dates=expiration.isoformat(),
            state="active",
            tradability="tradable",
        )
        instruments = instrument_response.get("data", {}).get("instruments", [])
        if not instruments:
            return []

        ids = [str(row["id"]) for row in instruments]
        quote_response = self.client.get_option_quotes(instrument_ids=ids)
        result_rows = quote_response.get("data", {}).get("results", [])

        quotes_by_id: dict[str, dict[str, Any]] = {}
        for result in result_rows:
            quote = result.get("quote") or {}
            instrument_id = quote.get("instrument_id")
            if instrument_id:
                quotes_by_id[str(instrument_id)] = quote

        normalized: list[OptionQuote] = []
        for instrument in instruments:
            instrument_id = str(instrument["id"])
            quote = quotes_by_id.get(instrument_id)
            if not quote:
                continue

            option_type = str(instrument["type"]).lower()
            if option_type not in {"call", "put"}:
                continue

            normalized.append(
                OptionQuote(
                    symbol=str(instrument.get("chain_symbol", symbol)),
                    expiration=expiration,
                    strike=float(instrument["strike_price"]),
                    option_type=option_type,
                    bid=float(quote["bid_price"]),
                    ask=float(quote["ask_price"]),
                    delta=float(quote["delta"]),
                )
            )

        return normalized
