import unittest

from regime_selector import RegimeInputs, classify_regime


class RegimeSelectorTests(unittest.TestCase):
    def test_neutral_high_iv_prefers_condor(self):
        d = classify_regime(RegimeInputs(0.05, 0.80))
        self.assertEqual(d.preferred_strategy, "iron_condor")

    def test_moderate_bullish_prefers_credit_spread(self):
        d = classify_regime(RegimeInputs(0.35, 0.50))
        self.assertEqual(d.preferred_strategy, "bull_put_credit_spread")

    def test_strong_bearish_prefers_debit_spread(self):
        d = classify_regime(RegimeInputs(-0.80, 0.50))
        self.assertEqual(d.preferred_strategy, "bear_put_debit_spread")

    def test_event_without_term_structure_blocks_trade(self):
        d = classify_regime(RegimeInputs(0.0, 0.8, event_risk=True))
        self.assertEqual(d.regime, "no_trade")


if __name__ == "__main__":
    unittest.main()
