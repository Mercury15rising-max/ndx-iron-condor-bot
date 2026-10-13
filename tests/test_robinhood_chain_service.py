import unittest
from datetime import date

from robinhood_chain_service import RobinhoodChainService


class FakeRobinhoodMCP:
    def get_option_chains(self, symbol):
        return {"symbol": symbol}

    def get_option_instruments(self, symbol, expiration, option_type=None):
        return [
            {
                "id": "p1",
                "strike_price": "25000",
                "option_type": "put",
            },
            {
                "id": "c1",
                "strike_price": "25500",
                "option_type": "call",
            },
        ]

    def get_option_quotes(self, instrument_ids):
        return [
            {
                "instrument_id": "p1",
                "bid_price": "4.00",
                "ask_price": "4.40",
                "delta": "-0.12",
            },
            {
                "instrument_id": "c1",
                "bid_price": "3.50",
                "ask_price": "3.90",
                "delta": "0.11",
            },
        ]

    def review_option_order(self, order):
        return {"status": "reviewed", "order": order}

    def place_option_order(self, order):
        return {"status": "placed", "order": order}


class RobinhoodChainServiceTests(unittest.TestCase):
    def test_builds_normalized_quotes(self):
        service = RobinhoodChainService(FakeRobinhoodMCP())
        expiration = date(2026, 10, 16)

        quotes = service.get_chain("NDX", expiration)

        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0].strike, 25000.0)
        self.assertEqual(quotes[0].option_type, "put")
        self.assertEqual(quotes[1].option_type, "call")
        self.assertAlmostEqual(quotes[1].delta, 0.11)


if __name__ == "__main__":
    unittest.main()
