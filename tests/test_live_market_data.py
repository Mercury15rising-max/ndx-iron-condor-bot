import unittest
from datetime import date

from live_market_data import RobinhoodMarketDataProvider


class FakeRobinhoodClient:
    def get_option_chain(self, symbol, expiration):
        return [
            {
                "strike": "25000",
                "option_type": "put",
                "bid": "4.00",
                "ask": "4.40",
                "delta": "-0.12",
            },
            {
                "strike": "25500",
                "option_type": "call",
                "bid": "3.50",
                "ask": "3.90",
                "delta": "0.11",
            },
        ]


class LiveMarketDataTests(unittest.TestCase):
    def test_normalizes_raw_rows(self):
        expiration = date(2026, 10, 16)
        provider = RobinhoodMarketDataProvider(FakeRobinhoodClient())
        quotes = provider.get_option_chain("NDX", expiration)

        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0].strike, 25000.0)
        self.assertEqual(quotes[1].option_type, "call")


if __name__ == "__main__":
    unittest.main()
