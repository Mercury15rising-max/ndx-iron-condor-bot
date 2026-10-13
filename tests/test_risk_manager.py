import unittest
from datetime import date

from paper_market_data import PaperMarketDataProvider
from strategy import build_iron_condor
from risk_manager import evaluate_trade

class RiskManagerTests(unittest.TestCase):
    def setUp(self):
        expiration = date(2026, 10, 16)
        chain = PaperMarketDataProvider().get_option_chain("NDX", expiration)
        self.condor = build_iron_condor(chain, 0.10, 0.15, 25)

    def test_rejects_trade_above_risk_limit(self):
        decision = evaluate_trade(
            self.condor,
            max_risk_per_trade=100,
            daily_realized_pnl=0,
            max_daily_loss=750,
            open_positions=0,
            max_open_positions=1,
            trades_today=0,
            max_trades_per_day=1,
        )
        self.assertFalse(decision.approved)

    def test_approves_trade_when_limits_allow(self):
        decision = evaluate_trade(
            self.condor,
            max_risk_per_trade=5000,
            daily_realized_pnl=0,
            max_daily_loss=750,
            open_positions=0,
            max_open_positions=1,
            trades_today=0,
            max_trades_per_day=1,
        )
        self.assertTrue(decision.approved)

if __name__ == "__main__":
    unittest.main()
