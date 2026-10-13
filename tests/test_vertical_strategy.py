import unittest
from datetime import date

from models import OptionQuote
from vertical_strategy import build_credit_spread, build_debit_spread


def q(strike, kind, bid, ask, delta):
    return OptionQuote("NDXP", date(2026, 10, 16), strike, kind, bid, ask, delta)


class VerticalStrategyTests(unittest.TestCase):
    def setUp(self):
        self.quotes = [
            q(90, "put", 0.8, 1.0, -0.10),
            q(95, "put", 1.8, 2.0, -0.20),
            q(100, "put", 4.8, 5.2, -0.50),
            q(100, "call", 4.8, 5.2, 0.50),
            q(105, "call", 1.8, 2.0, 0.20),
            q(110, "call", 0.8, 1.0, 0.10),
        ]

    def test_bull_put_credit_spread_defined_risk(self):
        spread = build_credit_spread(self.quotes, bullish=True, short_delta=0.20, wing_width=5)
        self.assertEqual(spread.premium_type, "credit")
        self.assertEqual(spread.direction, "bullish")
        self.assertGreater(spread.max_profit, 0)
        self.assertGreater(spread.max_loss, 0)

    def test_bull_call_debit_spread_defined_risk(self):
        spread = build_debit_spread(self.quotes, bullish=True, long_delta=0.50, wing_width=5)
        self.assertEqual(spread.premium_type, "debit")
        self.assertEqual(spread.direction, "bullish")
        self.assertGreater(spread.max_profit, 0)
        self.assertGreater(spread.max_loss, 0)


if __name__ == "__main__":
    unittest.main()
