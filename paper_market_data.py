from datetime import date
from market_data import MarketDataProvider
from models import OptionQuote

class PaperMarketDataProvider(MarketDataProvider):
    """Deterministic sample chain for dry-run development and tests."""

    def get_option_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        if symbol != "NDX":
            raise ValueError("Paper provider currently supports NDX only.")

        return [
            OptionQuote(symbol, expiration, 24500, "put", 6.00, 6.40, -0.08),
            OptionQuote(symbol, expiration, 24525, "put", 7.20, 7.60, -0.10),
            OptionQuote(symbol, expiration, 24550, "put", 8.80, 9.20, -0.12),
            OptionQuote(symbol, expiration, 24575, "put", 10.50, 11.00, -0.15),
            OptionQuote(symbol, expiration, 24600, "put", 12.50, 13.00, -0.18),
            OptionQuote(symbol, expiration, 25200, "call", 12.20, 12.70, 0.18),
            OptionQuote(symbol, expiration, 25225, "call", 10.30, 10.80, 0.15),
            OptionQuote(symbol, expiration, 25250, "call", 8.60, 9.00, 0.12),
            OptionQuote(symbol, expiration, 25275, "call", 7.00, 7.40, 0.10),
            OptionQuote(symbol, expiration, 25300, "call", 5.80, 6.20, 0.08),
        ]
