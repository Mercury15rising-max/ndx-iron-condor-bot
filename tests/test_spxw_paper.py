import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from spxw_paper import initial_state, overnight_session, step

NOW = datetime(2026, 10, 14, 5, 30, tzinfo=timezone.utc)


def snapshot(now=NOW):
    return {
        "session_open": True, "session_observed_at": now.isoformat(), "complete": True,
        "chains": [{"id": "chain", "symbol": "SPXW", "settle_on_open": False,
                    "extended_hours_state": "enabled", "can_open_position": True,
                    "trade_value_multiplier": "100.0000"}],
        "instruments": [
            {"id": id_, "chain_id": "chain", "chain_symbol": "SPXW", "type": "call",
             "expiration_date": "2026-10-15", "strike_price": strike,
             "trade_value_multiplier": "100", "state": "active", "tradability": "tradable"}
            for id_, strike in [("long", "7840"), ("short", "7845")]],
        "quotes": [
            {"instrument_id": id_, "bid_price": bid, "ask_price": ask, "delta": delta,
             "bid_size": 2, "ask_size": 2, "updated_at": now.isoformat()}
            for id_, bid, ask, delta in [("long", "2.0", "2.2", "0.30"),
                                       ("short", "1.0", "1.2", "0.27")]],
    }


class SPXWPaperTests(unittest.TestCase):
    def opened(self):
        return step(initial_state(), snapshot(), NOW)[0]

    def test_entry_cost_and_audit(self):
        state, event = step(initial_state(), snapshot(), NOW)
        self.assertEqual(event["action"], "PAPER_ENTRY")
        self.assertEqual(float(state["balance"]), 2878)
        self.assertEqual(float(state["position"]["entry_cost"]), 122)
        self.assertEqual(state["position"]["short"]["id"], "short")
        self.assertTrue(event["paper_only"])

    def test_bad_quotes_rejected(self):
        for changes in [
            {"updated_at": (NOW - timedelta(seconds=61)).isoformat()},
            {"updated_at": (NOW + timedelta(seconds=1)).isoformat()},
            {"bid_price": "3"}, {"ask_size": 0}, {"bid_price": "NaN"},
            {"delta": None}, {"updated_at": "bad"}, {"bid_price": "0"},
        ]:
            with self.subTest(changes=changes):
                data = snapshot()
                data["quotes"][0].update(changes)
                state, event = step(initial_state(), data, NOW)
                self.assertEqual(event["action"], "NO_TRADE")
                self.assertIsNone(state["position"])

    def test_60_second_boundary(self):
        data = snapshot()
        for q in data["quotes"]:
            q["updated_at"] = (NOW - timedelta(seconds=60)).isoformat()
        self.assertEqual(step(initial_state(), data, NOW)[1]["action"], "PAPER_ENTRY")

    def test_fee_inclusive_cost_cap(self):
        for ask, expected in [("2.48", "PAPER_ENTRY"), ("2.49", "NO_TRADE")]:
            data = snapshot()
            data["quotes"][0]["ask_price"] = ask
            self.assertEqual(step(initial_state(), data, NOW)[1]["action"], expected)

    def test_negative_premium_rejected(self):
        data = snapshot()
        data["quotes"][1].update(bid_price="2.3", ask_price="2.4")
        self.assertEqual(step(initial_state(), data, NOW)[1]["action"], "NO_TRADE")

    def test_missing_protective_quote_rejected(self):
        data = snapshot()
        data["quotes"].pop()
        state, event = step(initial_state(), data, NOW)
        self.assertEqual(event["action"], "NO_TRADE")
        self.assertIsNone(state["position"])

    def test_stop_uses_observed_loss_not_threshold(self):
        later = NOW + timedelta(minutes=10)
        state, event = step(self.opened(), snapshot(later), later)
        self.assertEqual(event["action"], "STOP_LOSS")
        self.assertEqual(float(event["net_pnl"]), -44)
        self.assertAlmostEqual(float(event["loss_beyond_threshold"]), 7.4)
        self.assertEqual(float(state["balance"]), 2956)
        self.assertEqual(state["completed"], 1)
        self.assertIsNone(state["position"])

    def test_exact_stop_boundary_and_priority(self):
        later = NOW + timedelta(hours=1)
        data = snapshot(later)
        data["quotes"][0].update(bid_price="2.074", ask_price="2.2")
        event = step(self.opened(), data, later)[1]
        self.assertEqual(event["action"], "STOP_LOSS")
        self.assertEqual(float(event["net_pnl"]), -36.6)

    def test_hold_then_time_exit_and_state_roundtrip(self):
        state = json.loads(json.dumps(self.opened()))
        for minutes, action in [(59, "HOLD"), (60, "TIME_EXIT")]:
            later = NOW + timedelta(minutes=minutes)
            data = snapshot(later)
            data["quotes"][0].update(bid_price="2.3", ask_price="2.5")
            state, event = step(state, data, later)
            self.assertEqual(event["action"], action)
        self.assertEqual(float(state["balance"]), 2986)

    def test_stale_exit_keeps_position(self):
        opened = self.opened()
        later = NOW + timedelta(hours=1)
        data = snapshot(later)
        data["quotes"] = []
        state, event = step(opened, data, later)
        self.assertEqual(event["action"], "UNRESOLVED")
        self.assertEqual(state["position"], opened["position"])
        self.assertEqual(state["balance"], opened["balance"])

    def test_order_independent_and_tie_favors_lower_strike(self):
        data = snapshot()
        data["quotes"][0]["delta"] = "0.31"
        data["quotes"][1]["delta"] = "0.29"
        data["instruments"].reverse()
        data["quotes"].reverse()
        self.assertEqual(step(initial_state(), data, NOW)[0]["position"]["long"]["id"], "long")

    def test_metadata_and_completeness_fail_closed(self):
        for kind in ("am", "zero_dte", "multiplier", "incomplete", "duplicate", "wing"):
            data = snapshot()
            if kind == "am":
                data["chains"][0]["settle_on_open"] = True
            elif kind == "zero_dte":
                for i in data["instruments"]:
                    i["expiration_date"] = "2026-10-14"
            elif kind == "multiplier":
                data["chains"][0]["trade_value_multiplier"] = "10"
            elif kind == "incomplete":
                data["complete"] = False
            elif kind == "duplicate":
                data["instruments"].append(dict(data["instruments"][0]))
            else:
                data["instruments"][1]["strike_price"] = "7850"
            with self.subTest(kind=kind):
                self.assertEqual(step(initial_state(), data, NOW)[1]["action"], "NO_TRADE")

    def test_risk_and_completed_limits(self):
        for kind in ("cash", "daily", "complete"):
            state = initial_state()
            if kind == "cash":
                state["balance"] = "100"
            elif kind == "daily":
                state["daily_pnl"]["2026-10-14"] = "-300"
            else:
                state["completed"] = 30
            result, event = step(state, snapshot(), NOW)
            self.assertIsNone(result["position"])
            self.assertIn(event["action"], ("NO_TRADE", "COMPLETE"))

    def test_replay_rejected(self):
        with self.assertRaises(ValueError):
            step(self.opened(), snapshot(), NOW)

    def test_holiday_and_weekend_rejected(self):
        data = snapshot()
        data["session_open"] = False
        self.assertEqual(step(initial_state(), data, NOW)[1]["action"], "UNAVAILABLE")
        self.assertIsNone(overnight_session(NOW + timedelta(days=3)))
        self.assertEqual(overnight_session(NOW - timedelta(hours=5)), "2026-10-14")

    def test_cli_persists_and_refuses_reset_or_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, ledger = Path(tmp) / "snapshot.json", Path(tmp) / "state.json"
            path.write_text(json.dumps(snapshot()))
            cmd = [sys.executable, "spxw_paper.py", str(path), "--state", str(ledger)]
            env = dict(os.environ, TRADING_MODE="paper", ROBINHOOD_LIVE_ORDERS="false")
            self.assertNotEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 0)
            result = subprocess.run(cmd + ["--init"], env=env, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            saved = ledger.read_text()
            self.assertNotEqual(subprocess.run(cmd + ["--init"], env=env,
                                               capture_output=True).returncode, 0)
            env["ROBINHOOD_LIVE_ORDERS"] = "true"
            self.assertNotEqual(subprocess.run(cmd, env=env, capture_output=True).returncode, 0)
            self.assertEqual(ledger.read_text(), saved)


if __name__ == "__main__":
    unittest.main()
