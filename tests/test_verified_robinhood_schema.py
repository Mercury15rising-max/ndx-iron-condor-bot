import unittest
from datetime import date

from live_market_data import RobinhoodMarketDataProvider


class FakeVerifiedRobinhoodClient:
    def get_option_instruments(self, **kwargs):
        return {
            "data": {
                "instruments": [
                    {
                        "id": "p1",
                        "chain_symbol": "NDXP",
                        "expiration_date": "2026-10-16",
                        "strike_price": "30000.0000",
                        "type": "put",
                    },
                    {
                        "id": "c1",
                        "chain_symbol": "NDXP",
                        "expiration_date": "2026-10-16",
                        "strike_price": "31000.0000",
                        "type": "call",
                    },
                ]
            }
        }

    def get_option_quotes(self, **kwargs):
        return {
            "data": {
                "results": [
                    {
                        "quote": {
                            "instrument_id": "p1",
                            "bid_price": "4.00",
                            "ask_price": "4.40",
                            "delta": "-0.12",
                        },
                        "close": {"price": "3.50"},
                    },
                    {
                        "quote": {
                            "instrument_id": "c1",
                            "bid_price": "3.50",
                            "ask_price": "3.90",
                            "delta": "0.11",
                        },
                        "close": {"price": "3.00"},
                    },
                ]
            }
        }


class VerifiedRobinhoodSchemaTests(unittest.TestCase):
    def test_normalizes_verified_nested_shapes(self):
        provider = RobinhoodMarketDataProvider(FakeVerifiedRobinhoodClient())
        quotes = provider.get_option_chain("NDXP", date(2026, 10, 16))

        self.assertEqual(len(quotes), 2)
        self.assertEqual(quotes[0].symbol, "NDXP")
        self.assertEqual(quotes[0].strike, 30000.0)
        self.assertAlmostEqual(quotes[0].delta, -0.12)
        self.assertEqual(quotes[1].option_type, "call")


if __name__ == "__main__":
    unittest.main()
