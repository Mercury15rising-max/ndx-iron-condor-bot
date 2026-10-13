import unittest
from datetime import date

from candidate_scanner import scan_candidates, best_candidate_or_none
from models import OptionQuote


class CandidateScannerTests(unittest.TestCase):
    def setUp(self):
        expiration = date(2026, 10, 16)
        self.quotes = [
            OptionQuote("NDXP", expiration, 29950, "put", 30.0, 31.0, -0.09),
            OptionQuote("NDXP", expiration, 29975, "put", 35.0, 36.0, -0.12),
            OptionQuote("NDXP", expiration, 30000, "put", 40.0, 41.0, -0.14),
            OptionQuote("NDXP", expiration, 30025, "put", 45.0, 46.0, -0.17),
            OptionQuote("NDXP", expiration, 31200, "call", 39.0, 40.0, 0.15),
            OptionQuote("NDXP", expiration, 31225, "call", 35.0, 36.0, 0.13),
            OptionQuote("NDXP", expiration, 31250, "call", 31.0, 32.0, 0.11),
            OptionQuote("NDXP", expiration, 31275, "call", 27.0, 28.0, 0.09),
        ]

    def test_returns_only_risk_approved_candidates(self):
        candidates = scan_candidates(
            quotes=self.quotes,
            wing_widths=[25, 50],
            delta_ranges=[(0.10, 0.15), (0.12, 0.14)],
            max_risk_per_trade=5000,
            max_daily_loss=750,
        )
        self.assertTrue(candidates)
        self.assertTrue(all(c.condor.max_loss <= 5000 for c in candidates))

    def test_returns_no_trade_when_risk_limit_too_low(self):
        best = best_candidate_or_none(
            quotes=self.quotes,
            wing_widths=[25, 50],
            delta_ranges=[(0.10, 0.15)],
            max_risk_per_trade=100,
            max_daily_loss=750,
        )
        self.assertIsNone(best)

    def test_sorted_best_score_first(self):
        candidates = scan_candidates(
            quotes=self.quotes,
            wing_widths=[25, 50],
            delta_ranges=[(0.10, 0.15)],
            max_risk_per_trade=5000,
            max_daily_loss=750,
        )
        scores = [c.score for c in candidates]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
