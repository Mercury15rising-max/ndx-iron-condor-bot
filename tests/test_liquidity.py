import unittest
from datetime import date

from liquidity import LiquidityRules, filter_liquid_quotes
from models import OptionQuote


class LiquidityTests(unittest.TestCase):
    def test_filters_wide_quotes(self):
        expiration = date(2026, 10, 16)
        quotes = [
            OptionQuote("NDX", expiration, 25000, "put", 4.00, 4.50, -0.12),
            OptionQuote("NDX", expiration, 24975, "put", 1.00, 5.00, -0.10),
        ]

        filtered = filter_liquid_quotes(
            quotes,
            LiquidityRules(max_bid_ask_width=1.00, min_bid=0.10),
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].strike, 25000)


if __name__ == "__main__":
    unittest.main()
