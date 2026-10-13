from datetime import date
from typing import Protocol, Any

from market_data import MarketDataProvider
from models import OptionQuote


class RobinhoodOptionsClient(Protocol):
    def get_option_chain(self, symbol: str, expiration: date) -> list[dict[str, Any]]:
        """Return raw option-chain rows from an authenticated Robinhood adapter."""
        ...


class RobinhoodMarketDataProvider(MarketDataProvider):
    """Normalize Robinhood option-chain data into the bot's internal model.

    The actual MCP transport is intentionally injected instead of hard-coded.
    This keeps strategy code testable and prevents accidental live-trading coupling.
    """

    def __init__(self, client: RobinhoodOptionsClient):
        self.client = client

    def get_option_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        rows = self.client.get_option_chain(symbol, expiration)
        quotes: list[OptionQuote] = []

        for row in rows:
            quotes.append(
                OptionQuote(
                    symbol=symbol,
                    expiration=expiration,
                    strike=float(row["strike"]),
                    option_type=str(row["option_type"]).lower(),
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    delta=float(row["delta"]),
                )
            )

        return quotes
