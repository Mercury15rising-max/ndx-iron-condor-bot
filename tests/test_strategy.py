import unittest
from datetime import date

from paper_market_data import PaperMarketDataProvider
from strategy import build_iron_condor

class StrategyTests(unittest.TestCase):
    def test_builds_positive_credit_condor(self):
        expiration = date(2026, 10, 16)
        chain = PaperMarketDataProvider().get_option_chain("NDX", expiration)

        condor = build_iron_condor(
            chain,
            short_delta_min=0.10,
            short_delta_max=0.15,
            wing_width=25,
        )

        self.assertEqual(condor.expiration, expiration)
        self.assertGreater(condor.net_credit, 0)
        self.assertGreater(condor.max_profit, 0)
        self.assertGreater(condor.max_loss, 0)
        self.assertLess(condor.long_put.strike, condor.short_put.strike)
        self.assertGreater(condor.long_call.strike, condor.short_call.strike)

if __name__ == "__main__":
    unittest.main()
