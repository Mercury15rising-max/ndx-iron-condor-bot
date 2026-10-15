"""Offline synthetic feed failures; no live market data or trading access."""
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timezone
import unittest

from liquidity import LiquidityRules, is_liquid
from live_market_data import RobinhoodMarketDataProvider
from market_schedule import evaluate_market_session
from models import OptionQuote
from safety_gate import evaluate_entry_safety


EXPIRY = date(2026, 10, 16)
STAMP = "2026-10-14T14:00:00.123456789Z"


class PagedClient:
    def __init__(self, count=205):
        self.rows = [dict(id=f"id-{n}", chain_symbol="NDXP",
                          expiration_date=EXPIRY.isoformat(), strike_price=str(29000+n*5),
                          type="call", state="active", tradability="tradable")
                     for n in range(count)]
        self.requests = []
        self.batches = []
        self.quote_edit = lambda quotes: quotes
        self.repeat_cursor = False

    def get_option_instruments(self, **request):
        self.requests.append(request)
        # Reproduce the observed upstream filter inconsistency.
        if "tradability" in request:
            return {"data": {"instruments": []}}
        start = int(request.get("cursor", "0"))
        end = start + 100
        data = {"instruments": deepcopy(self.rows[start:end])}
        if end < len(self.rows):
            data["next"] = "100" if self.repeat_cursor else str(end)
        return {"data": data}

    def get_option_quotes(self, *, instrument_ids):
        self.batches.append(instrument_ids)
        quotes = [dict(instrument_id=i, bid_price="3", ask_price="3.1", delta="0.3",
                       updated_at=STAMP, open_interest="100", volume="20")
                  for i in reversed(instrument_ids)]
        return {"data": {"results": [{"quote": q} for q in self.quote_edit(quotes)]}}


class FeedRegressionTests(unittest.TestCase):
    def test_all_pages_bounded_quote_batches_and_original_timestamps(self):
        client = PagedClient()
        rows = RobinhoodMarketDataProvider(client).get_option_chain("NDXP", EXPIRY)
        self.assertEqual(len(rows), 205)
        self.assertEqual([len(b) for b in client.batches], [100, 100, 5])
        self.assertEqual([r.get("cursor") for r in client.requests], [None, "100", "200"])
        self.assertEqual([r.strike for r in rows], [29000+n*5 for n in range(205)])
        self.assertTrue(all(r.quote_timestamp == STAMP for r in rows))

    def test_local_tradability_filter_excludes_ineligible_rows(self):
        client = PagedClient(3)
        client.rows[0]["tradability"] = "untradable"
        client.rows[1]["state"] = "inactive"
        rows = RobinhoodMarketDataProvider(client).get_option_chain("NDXP", EXPIRY)
        self.assertEqual(len(rows), 1)
        self.assertEqual(client.batches, [["id-2"]])

    def test_null_delta_missing_quote_and_duplicate_quote_fail_closed(self):
        edits = [lambda qs: [{**q, "delta": None} for q in qs],
                 lambda qs: qs[:-1], lambda qs: qs + [qs[0]],
                 lambda qs: [{**q, "bid_price": "NaN"} for q in qs],
                 lambda qs: [{**q, "ask_price": "2"} for q in qs]]
        for edit in edits:
            with self.subTest(edit=edit):
                client = PagedClient(2)
                client.quote_edit = edit
                with self.assertRaises(ValueError):
                    RobinhoodMarketDataProvider(client).get_option_chain("NDXP", EXPIRY)

    def test_bad_pagination_and_duplicate_contract_fail_closed(self):
        for mode in ("cursor", "duplicate", "expiry"):
            with self.subTest(mode=mode):
                client = PagedClient()
                if mode == "cursor":
                    client.repeat_cursor = True
                elif mode == "duplicate":
                    client.rows[100]["id"] = client.rows[0]["id"]
                else:
                    client.rows[0]["expiration_date"] = "2026-10-15"
                with self.assertRaises(ValueError):
                    RobinhoodMarketDataProvider(client).get_option_chain("NDXP", EXPIRY)
                self.assertEqual(client.batches, [])


class ValidationRegressionTests(unittest.TestCase):
    def test_liquidity_rejects_crossed_nonfinite_and_unknown_required_metrics(self):
        q = OptionQuote("NDXP", EXPIRY, 100, "call", 3, 3.1, .3)
        for values in ({"ask": 2}, {"bid": float("nan")}, {"ask": float("inf")},
                       {"bid": 0, "ask": 0}):
            with self.subTest(values=values):
                self.assertFalse(is_liquid(replace(q, **values), LiquidityRules()))
        self.assertFalse(is_liquid(q, LiquidityRules(min_open_interest=50)))
        self.assertFalse(is_liquid(q, LiquidityRules(min_volume=10)))
        self.assertTrue(is_liquid(q, LiquidityRules()))
        self.assertTrue(is_liquid(replace(q, open_interest=50, volume=10),
                                  LiquidityRules(min_open_interest=50, min_volume=10)))

    def test_safety_rejects_ambiguous_and_future_times(self):
        now = datetime(2026, 10, 14, 14, tzinfo=timezone.utc)
        for quote, observed in ((now.replace(tzinfo=None), now),
                                (now, now.replace(tzinfo=None)),
                                (now.replace(minute=1), now)):
            self.assertEqual(evaluate_entry_safety(quote_timestamp=quote, now=observed).action,
                             "reject")

    def test_regular_schedule_rejects_weekend_holiday_and_after_early_close(self):
        for day, hour in (("2026-10-17", 15), ("2026-07-03", 15), ("2026-11-27", 18)):
            now = datetime.fromisoformat(f"{day}T{hour}:00:00+00:00")
            result = evaluate_market_session(now, is_zero_dte=False)
            self.assertFalse(result.allow_new_entries)
            self.assertFalse(result.monitor_positions)

    def test_early_close_exit_and_chicago_calendar_boundaries(self):
        # Nov 27 closes at 13:00 Eastern; exit-only starts at 12:30.
        result = evaluate_market_session(datetime.fromisoformat("2026-11-27T17:35:00+00:00"),
                                         is_zero_dte=False)
        self.assertTrue(result.exit_only)
        self.assertFalse(result.allow_new_entries)
        # 08:45 Chicago is open, although it precedes a hard-coded 09:30 clock.
        result = evaluate_market_session(datetime.fromisoformat("2026-10-14T13:45:00+00:00"),
                                         timezone_name="America/Chicago", is_zero_dte=False)
        self.assertTrue(result.monitor_positions)
        self.assertFalse(result.allow_new_entries)


if __name__ == "__main__":
    unittest.main()
