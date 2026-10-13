import unittest
from datetime import date, datetime, timedelta, timezone

from event_filter import ScheduledEvent
from multi_index_scanner import scan_index_watchlist
from models import OptionQuote


class FakeProvider:
    def get_option_chain(self, symbol, expiration):
        return [
            OptionQuote(symbol, expiration, 100, "put", 1.0, 1.1, -0.10, 0.20, 500, 100),
            OptionQuote(symbol, expiration, 105, "put", 2.0, 2.1, -0.15, 0.21, 500, 100),
            OptionQuote(symbol, expiration, 110, "call", 2.0, 2.1, 0.15, 0.21, 500, 100),
            OptionQuote(symbol, expiration, 115, "call", 1.0, 1.1, 0.10, 0.20, 500, 100),
        ]


class HardenedScannerTests(unittest.TestCase):
    def test_event_window_blocks_entries(self):
        now = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)
        results = scan_index_watchlist(
            provider=FakeProvider(),
            expirations={"NDXP": date(2026, 10, 16)},
            base_max_risk_per_trade=10000,
            max_daily_loss=750,
            condor_wing_widths=[5],
            condor_delta_ranges=[(0.10, 0.15)],
            butterfly_wing_widths=[5],
            butterfly_centers={},
            max_bid_ask_width=2.5,
            min_bid=0.1,
            now=now,
            scheduled_events=[ScheduledEvent("CPI", now)],
        )
        self.assertEqual(results, [])

    def test_loss_cooldown_blocks_entries(self):
        now = datetime(2026, 10, 13, 14, 0, tzinfo=timezone.utc)
        results = scan_index_watchlist(
            provider=FakeProvider(),
            expirations={"NDXP": date(2026, 10, 16)},
            base_max_risk_per_trade=10000,
            max_daily_loss=750,
            condor_wing_widths=[5],
            condor_delta_ranges=[(0.10, 0.15)],
            butterfly_wing_widths=[5],
            butterfly_centers={},
            max_bid_ask_width=2.5,
            min_bid=0.1,
            now=now,
            last_stop_time=now - timedelta(minutes=10),
            loss_cooldown_minutes=60,
        )
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
