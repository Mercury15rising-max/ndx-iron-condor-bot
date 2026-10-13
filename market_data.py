from abc import ABC, abstractmethod
from datetime import date
from models import OptionQuote

class MarketDataProvider(ABC):
    @abstractmethod
    def get_option_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        """Return normalized option quotes for one symbol and expiration."""
        raise NotImplementedError
