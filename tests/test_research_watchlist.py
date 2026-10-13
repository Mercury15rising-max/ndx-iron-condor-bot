import tempfile
import unittest

from paper_journal import PaperJournal
from research_context import ResearchSnapshot, journal_research_snapshot
from research_watchlist import DEFAULT_RESEARCH_WATCHLIST


class ResearchWatchlistTests(unittest.TestCase):
    def test_soxx_is_context_only(self):
        soxx = next(x for x in DEFAULT_RESEARCH_WATCHLIST if x.symbol == "SOXX")
        self.assertEqual(soxx.asset_type, "ETF")
        self.assertEqual(soxx.role, "context_only")

    def test_crdo_and_sitm_are_context_only(self):
        roles = {x.symbol: x.role for x in DEFAULT_RESEARCH_WATCHLIST}
        self.assertEqual(roles["CRDO"], "context_only")
        self.assertEqual(roles["SITM"], "context_only")

    def test_meta_is_context_only(self):
        roles = {x.symbol: x.role for x in DEFAULT_RESEARCH_WATCHLIST}
        self.assertEqual(roles["META"], "context_only")

    def test_semiconductor_research_feeds_are_context_only(self):
        roles = {x.symbol: x.role for x in DEFAULT_RESEARCH_WATCHLIST}
        for symbol in ("AVGO", "AMD", "MU", "TSM", "QCOM", "AMAT", "LRCX", "KLAC"):
            self.assertEqual(roles[symbol], "context_only")

    def test_research_snapshot_is_journaled_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = PaperJournal(f"{tmp}/journal.jsonl")
            journal_research_snapshot(
                journal,
                ResearchSnapshot(
                    symbol="SOXX",
                    underlying_price=300.0,
                    implied_volatility=0.25,
                    put_call_skew=0.03,
                    average_bid_ask_width=0.15,
                    option_volume=1000,
                    open_interest=5000,
                    metadata={"source": "paper"},
                ),
            )
            text = open(f"{tmp}/journal.jsonl", encoding="utf-8").read()
            self.assertIn('"event": "research_snapshot"', text)
            self.assertIn('"strategy": "research_context"', text)


if __name__ == "__main__":
    unittest.main()
