import unittest
from datetime import date

from butterfly_strategy import build_iron_butterfly
from models import OptionQuote


class IronButterflyTests(unittest.TestCase):
    def test_builds_defined_risk_butterfly(self):
        expiration = date(2026, 10, 16)
        quotes = [
            OptionQuote("NDXP", expiration, 30625, "put", 78.0, 80.0, -0.40),
            OptionQuote("NDXP", expiration, 30650, "put", 88.0, 90.0, -0.47),
            OptionQuote("NDXP", expiration, 30675, "put", 99.0, 101.0, -0.50),
            OptionQuote("NDXP", expiration, 30675, "call", 99.0, 101.0, 0.50),
            OptionQuote("NDXP", expiration, 30700, "call", 88.0, 90.0, 0.47),
            OptionQuote("NDXP", expiration, 30725, "call", 78.0, 80.0, 0.40),
        ]

        butterfly = build_iron_butterfly(
            quotes,
            center_strike=30675,
            wing_width=50,
        )

        self.assertEqual(butterfly.short_put.strike, 30675)
        self.assertEqual(butterfly.short_call.strike, 30675)
        self.assertLess(butterfly.long_put.strike, butterfly.short_put.strike)
        self.assertGreater(butterfly.long_call.strike, butterfly.short_call.strike)
        self.assertGreater(butterfly.net_credit, 0)
        self.assertGreater(butterfly.max_profit, 0)
        self.assertGreater(butterfly.max_loss, 0)


if __name__ == "__main__":
    unittest.main()
