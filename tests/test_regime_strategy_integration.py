import unittest
from datetime import date

from execution_plan import build_paper_execution_plan
from models import OptionQuote
from regime_selector import RegimeInputs, classify_regime
from strategy_selector import select_strategy_for_regime


def q(strike, kind, bid, ask, delta):
    return OptionQuote("NDXP", date(2026, 10, 16), strike, kind, bid, ask, delta)


class RegimeStrategyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.quotes = [
            q(90, "put", 0.8, 1.0, -0.10),
            q(95, "put", 1.8, 2.0, -0.20),
            q(100, "put", 4.8, 5.2, -0.50),
            q(100, "call", 4.8, 5.2, 0.50),
            q(105, "call", 1.8, 2.0, 0.20),
            q(110, "call", 0.8, 1.0, 0.10),
        ]

    def test_moderate_bullish_builds_bull_put_spread(self):
        regime = classify_regime(RegimeInputs(0.35, 0.50))
        selection = select_strategy_for_regime(
            self.quotes,
            regime,
            max_risk_per_trade=1000,
            max_daily_loss=750,
            vertical_wing_width=5,
        )
        self.assertIsNotNone(selection)
        self.assertEqual(selection.strategy, "bull_put_credit_spread")
        plan = build_paper_execution_plan(selection)
        self.assertEqual(len(plan.legs), 2)
        self.assertLessEqual(plan.max_loss, 1000)

    def test_event_calendar_placeholder_does_not_execute(self):
        regime = classify_regime(
            RegimeInputs(0.0, 0.8, event_risk=True, term_structure_signal=True)
        )
        selection = select_strategy_for_regime(
            self.quotes,
            regime,
            max_risk_per_trade=1000,
            max_daily_loss=750,
        )
        self.assertIsNone(selection)


if __name__ == "__main__":
    unittest.main()
