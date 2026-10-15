"""Synthetic data only. These tests make no market-performance or fill claims."""
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from exchange_session import bounds, session_at
from ndx_paper import initial_state, step
from paper_pipeline import build_snapshot
from paper_replay import accounting, new_archive, observe, replay
from test_ndx_paper import NOW, data

ROOT = Path(__file__).resolve().parents[1]


def bundle(now=NOW):
    """Three full historical sessions plus current completed bars, all synthetic."""
    prior = []
    day = now.date() - timedelta(days=1)
    while len(prior) < 3:
        if bounds(day):
            prior.insert(0, day)
        day -= timedelta(days=1)
    candles = []
    for day in prior + [now.date()]:
        start, end = bounds(day)
        close = start + timedelta(minutes=5)
        while close <= min(end, now):
            candles.append({"symbol": "QQQ", "timeframe_seconds": 300,
                            "close_time": close.isoformat(), "closed": True,
                            "open": "100", "high": "110", "low": "99", "close": "100",
                            "volume": "1000", "provider_extra": "preserved fixture metadata"})
            close += timedelta(minutes=5)
    candles[-1]["close"] = "110"
    options = data(now)
    for key in ("signal_bars", "signal_symbol", "session_open", "session_observed_at"):
        options.pop(key, None)
    return {"version": 1, "source": {"kind": "fixture", "name": "synthetic regression only"},
            "observed_at": now.isoformat(), "candles": candles, "options": options}


class PipelineTests(unittest.TestCase):
    def test_calendar_holiday_early_close_dst_and_weekend(self):
        self.assertIsNone(bounds(date(2026, 7, 3)))
        self.assertIsNone(bounds(date(2026, 10, 17)))
        self.assertEqual(bounds(date(2026, 11, 27))[1].hour, 18)
        self.assertIsNone(session_at(datetime(2026, 11, 27, 18, tzinfo=timezone.utc)))
        self.assertEqual(bounds(date(2026, 3, 6))[0].hour, 14)
        self.assertEqual(bounds(date(2026, 3, 9))[0].hour, 13)

    def test_three_sessions_preserved_and_no_fixture_default(self):
        b = bundle()
        with self.assertRaises(ValueError): build_snapshot(b, NOW)
        snapshot = build_snapshot(b, NOW, allow_fixtures=True)
        self.assertEqual(len(snapshot["provenance"]["completed_sessions"]), 3)
        self.assertEqual(snapshot["signal_bars"], b["candles"])
        self.assertEqual(snapshot["quotes"], b["options"]["quotes"])
        state, event = step(initial_state(), snapshot, NOW)
        self.assertEqual(event["action"], "PAPER_ENTRY")
        self.assertIsNotNone(state["position"])

    def test_missing_duplicate_future_misaligned_or_incomplete_candles(self):
        for kind in ("missing", "duplicate", "future", "misaligned", "incomplete", "ohlc"):
            b = bundle()
            if kind == "missing": b["candles"].pop(80)
            elif kind == "duplicate": b["candles"].insert(1, deepcopy(b["candles"][0]))
            elif kind == "future": b["candles"][-1]["close_time"] = (NOW+timedelta(minutes=5)).isoformat()
            elif kind == "misaligned": b["candles"][0]["close_time"] = (datetime.fromisoformat(b["candles"][0]["close_time"])+timedelta(seconds=1)).isoformat()
            elif kind == "incomplete": b["candles"].pop(0)
            else: b["candles"][0]["low"] = "101"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_snapshot(b, NOW, allow_fixtures=True)

    def test_quotes_missing_sizes_stale_crossed_or_duplicate(self):
        for kind in ("size", "stale", "crossed", "duplicate", "future"):
            b = bundle(); q = b["options"]["quotes"][0]
            if kind == "size": q.pop("bid_size")
            elif kind == "stale": q["updated_at"] = (NOW-timedelta(seconds=61)).isoformat()
            elif kind == "future": q["updated_at"] = (NOW+timedelta(seconds=1)).isoformat()
            elif kind == "crossed": q["bid_price"] = "999"
            else: b["options"]["quotes"].append(deepcopy(q))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                build_snapshot(b, NOW, allow_fixtures=True)

    def test_calendar_overrides_false_holiday_open_assertion(self):
        holiday = datetime(2026, 7, 3, 17, tzinfo=timezone.utc)
        s = data(); s["session_observed_at"] = holiday.isoformat()
        self.assertEqual(step(initial_state(), s, holiday)[1]["action"], "UNAVAILABLE")
        state, _ = step(initial_state(), data(), NOW)
        self.assertEqual(step(state, s, holiday.replace(year=2027))[1]["action"], "UNRESOLVED")

    def test_cross_engine_state_and_daily_accounting_corruption(self):
        import spxw_paper
        with self.assertRaises(ValueError):
            spxw_paper.step(initial_state(), {}, NOW)
        archive = observe(new_archive(), build_snapshot(bundle(), NOW, allow_fixtures=True), NOW)
        later = NOW + timedelta(minutes=10)
        archive = observe(archive, build_snapshot(bundle(later), later, allow_fixtures=True), later)
        state, report = replay(archive)
        self.assertEqual(report["completed_trades"], 1)
        state["daily_pnl"] = {}
        with self.assertRaises(ValueError): accounting(state)

    def test_malformed_metadata_fails_closed_in_both_engines(self):
        import spxw_paper
        from test_spxw_paper import snapshot, NOW as SPX_NOW
        for engine, fixture, when in ((sys.modules['ndx_paper'], data, NOW),
                                      (spxw_paper, snapshot, SPX_NOW)):
            for field in ('chains', 'instruments', 'quotes'):
                for malformed in (None, [None], [{'id': []} ]):
                    s = fixture(); s[field] = malformed
                    with self.subTest(engine=engine.__name__, field=field, malformed=malformed):
                        _, event = engine.step(engine.initial_state(), s, when)
                        self.assertIn(event['action'], ('NO_TRADE', 'UNAVAILABLE'))

    def test_persisted_cli_entry_exit_restart_and_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            snapshot = Path(tmp)/"fixture.json"; archive = Path(tmp)/"archive.json"
            env = dict(os.environ, TRADING_MODE="paper", ROBINHOOD_LIVE_ORDERS="false", ALLOW_0DTE="false")
            command = [sys.executable, str(ROOT/"paper_pipeline.py"), str(snapshot),
                       "--archive", str(archive), "--historical", "--allow-fixtures"]
            for i, now in enumerate((NOW, NOW+timedelta(minutes=10))):
                incoming = bundle(now)
                if i:
                    incoming['candles'] = []  # Exit must not wait for entry indicators.
                snapshot.write_text(json.dumps(incoming))
                result = subprocess.run(command + (["--init"] if i == 0 else []), env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["action"], "PAPER_ENTRY" if i == 0 else "STOP_LOSS")
            saved = json.loads(archive.read_text())
            state, report = replay(saved)
            self.assertEqual(report["completed_trades"], 1)
            self.assertFalse(report["unresolved_position"])
            cash = report["cash"]
            verified = subprocess.run([sys.executable, str(ROOT/"paper_replay.py"), str(archive)], env=env, capture_output=True, text=True)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertEqual(json.loads(verified.stdout)["cash"], cash)
            self.assertEqual(replay(saved), (state, report))
            before = archive.read_bytes()
            reset = subprocess.run(command+["--init"], env=env, capture_output=True)
            self.assertNotEqual(reset.returncode, 0)
            live = subprocess.run(command, env=dict(env, ROBINHOOD_LIVE_ORDERS="true"), capture_output=True)
            self.assertNotEqual(live.returncode, 0)
            self.assertEqual(before, archive.read_bytes())

    def test_missing_exit_quotes_persist_unresolved_without_history(self):
        s = build_snapshot(bundle(), NOW, allow_fixtures=True)
        state, _ = step(initial_state(), s, NOW)
        later = NOW + timedelta(minutes=10)
        b = bundle(later); b['candles'] = []; b['options']['quotes'] = []
        outgoing = build_snapshot(b, later, allow_fixtures=True, exit_only=True)
        next_state, event = step(state, outgoing, later)
        self.assertEqual(event['action'], 'UNRESOLVED')
        self.assertEqual(next_state['position'], state['position'])
        self.assertEqual(next_state['balance'], state['balance'])
