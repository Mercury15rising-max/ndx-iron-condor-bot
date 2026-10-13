import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from market_schedule import evaluate_market_session


class MarketScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("America/New_York")

    def dt(self, hour, minute):
        return datetime(2026, 10, 13, hour, minute, tzinfo=self.tz)

    def test_normal_entry_window(self):
        self.assertTrue(
            evaluate_market_session(self.dt(11, 0), is_zero_dte=False).allow_new_entries
        )

    def test_normal_entry_closes_at_230(self):
        result = evaluate_market_session(self.dt(14, 30), is_zero_dte=False)
        self.assertFalse(result.allow_new_entries)
        self.assertTrue(result.monitor_positions)

    def test_zero_dte_entry_closes_at_130(self):
        result = evaluate_market_session(self.dt(13, 30), is_zero_dte=True)
        self.assertFalse(result.allow_new_entries)
        self.assertTrue(result.monitor_positions)

    def test_opening_half_hour_is_monitor_only(self):
        result = evaluate_market_session(self.dt(9, 45), is_zero_dte=False)
        self.assertFalse(result.allow_new_entries)
        self.assertTrue(result.monitor_positions)

    def test_exit_only_after_330(self):
        result = evaluate_market_session(self.dt(15, 35), is_zero_dte=False)
        self.assertTrue(result.exit_only)
        self.assertFalse(result.allow_new_entries)


if __name__ == "__main__":
    unittest.main()
