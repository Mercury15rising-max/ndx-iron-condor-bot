import unittest

from index_watchlist import DEFAULT_INDEX_WATCHLIST, risk_limit_for_market


class IndexWatchlistTests(unittest.TestCase):
    def test_expected_markets_present(self):
        symbols = {m.chain_symbol for m in DEFAULT_INDEX_WATCHLIST}
        self.assertTrue({"NDXP", "NDX", "SPXW", "SPX", "XSP"} <= symbols)

    def test_xsp_uses_smaller_risk_budget(self):
        xsp = next(m for m in DEFAULT_INDEX_WATCHLIST if m.chain_symbol == "XSP")
        self.assertEqual(risk_limit_for_market(500, xsp), 250)


if __name__ == "__main__":
    unittest.main()
