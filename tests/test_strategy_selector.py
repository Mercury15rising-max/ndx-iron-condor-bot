import unittest
from datetime import date

from models import OptionQuote
from strategy_selector import select_best_strategy


class StrategySelectorTests(unittest.TestCase):
    def setUp(self):
        expiration = date(2026, 10, 16)
        self.quotes = [
            OptionQuote("NDXP", expiration, 29950, "put", 30, 31, -0.09),
            OptionQuote("NDXP", expiration, 29975, "put", 35, 36, -0.12),
            OptionQuote("NDXP", expiration, 30000, "put", 40, 41, -0.14),
            OptionQuote("NDXP", expiration, 30650, "put", 88, 90, -0.47),
            OptionQuote("NDXP", expiration, 30675, "put", 99, 101, -0.50),
            OptionQuote("NDXP", expiration, 30675, "call", 99, 101, 0.50),
            OptionQuote("NDXP", expiration, 30700, "call", 88, 90, 0.47),
            OptionQuote("NDXP", expiration, 31200, "call", 39, 40, 0.15),
            OptionQuote("NDXP", expiration, 31225, "call", 35, 36, 0.13),
            OptionQuote("NDXP", expiration, 31250, "call", 31, 32, 0.11),
        ]

    def test_returns_best_strategy_or_none(self):
        result = select_best_strategy(
            quotes=self.quotes,
            condor_wing_widths=[25],
            condor_delta_ranges=[(0.10, 0.15)],
            butterfly_centers=[30675],
            butterfly_wing_widths=[25],
            max_risk_per_trade=5000,
            max_daily_loss=750,
        )
        self.assertIsNotNone(result)
        self.assertIn(result.strategy, {"iron_condor", "iron_butterfly"})

    def test_no_trade_when_risk_limit_too_low(self):
        result = select_best_strategy(
            quotes=self.quotes,
            condor_wing_widths=[25],
            condor_delta_ranges=[(0.10, 0.15)],
            butterfly_centers=[30675],
            butterfly_wing_widths=[25],
            max_risk_per_trade=10,
            max_daily_loss=750,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
