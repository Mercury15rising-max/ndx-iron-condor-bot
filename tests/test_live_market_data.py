import unittest
from datetime import date

from live_market_data import RobinhoodMarketDataProvider


class FakeRobinhoodClient:
    def __init__(self):
        self.instrument_request = None
        self.quote_request = None

    def get_option_instruments(
        self, *, chain_symbol, expiration_dates,
        state="active", cursor=None,
    ):
        self.instrument_request = (chain_symbol, expiration_dates, state)
        return {"data": {"instruments": [
            {"id": "put-id", "chain_symbol": chain_symbol,
             "expiration_date": expiration_dates, "state": "active", "tradability": "tradable",
             "strike_price": "25000", "type": "put"},
            {"id": "call-id", "chain_symbol": chain_symbol,
             "expiration_date": expiration_dates, "state": "active", "tradability": "tradable",
             "strike_price": "25500", "type": "call"},
        ]}}

    def get_option_quotes(self, *, instrument_ids):
        self.quote_request = instrument_ids
        # Reverse response order to verify quotes are joined by ID, not position.
        return {"data": {"results": [
            {"quote": {"instrument_id": "call-id", "bid_price": "3.50",
                       "ask_price": "3.90", "delta": "0.11"}},
            {"quote": {"instrument_id": "put-id", "bid_price": "4.00",
                       "ask_price": "4.40", "delta": "-0.12"}},
        ]}}


class LiveMarketDataTests(unittest.TestCase):
    def test_normalizes_raw_rows(self):
        expiration = date(2026, 10, 16)
        client = FakeRobinhoodClient()
        provider = RobinhoodMarketDataProvider(client)
        quotes = provider.get_option_chain("NDX", expiration)

        self.assertEqual(
            client.instrument_request,
            ("NDX", "2026-10-16", "active"),
        )
        self.assertEqual(client.quote_request, ["put-id", "call-id"])
        self.assertEqual(len(quotes), 2)
        self.assertEqual(
            [(q.symbol, q.expiration, q.strike, q.option_type,
              q.bid, q.ask, q.delta) for q in quotes],
            [
                ("NDX", expiration, 25000.0, "put", 4.0, 4.4, -0.12),
                ("NDX", expiration, 25500.0, "call", 3.5, 3.9, 0.11),
            ],
        )


if __name__ == "__main__":
    unittest.main()

