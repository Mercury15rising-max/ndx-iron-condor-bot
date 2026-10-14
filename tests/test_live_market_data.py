import unittest
from datetime import date

from live_market_data import RobinhoodMarketDataProvider


class FakeRobinhoodClient:
    def get_option_instruments(self, **kwargs):
        return {"data": {"instruments": [
            {"id": "p1", "chain_symbol": kwargs["chain_symbol"],
             "expiration_date": kwargs["expiration_dates"], "strike_price": "25000", "type": "put"},
            {"id": "c1", "chain_symbol": kwargs["chain_symbol"],
             "expiration_date": kwargs["expiration_dates"], "strike_price": "25500", "type": "call"},
        ]}}

    def get_option_quotes(self, **kwargs):
        return {"data": {"results": [
            {"quote": {"instrument_id": "p1", "bid_price": "4.00", "ask_price": "4.40", "delta": "-0.12"}},
            {"quote": {"instrument_id": "c1", "bid_price": "3.50", "ask_price": "3.90", "delta": "0.11"}},
        ]}}


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

