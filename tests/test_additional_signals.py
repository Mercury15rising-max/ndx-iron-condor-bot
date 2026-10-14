import unittest
from datetime import timedelta
from ema_signals import evaluate_setup
from test_ema_signals import bars
from test_spxw_paper import NOW, snapshot
from spxw_paper import initial_state, step


def candles(prices):
    return [{**b, "high": b["close"] + 1, "low": b["close"] - 1,
             "volume": 10, "volume_type": "trade"} for b in bars(prices)]


class AdditionalSignalsTests(unittest.TestCase):
    def test_vwap_flip_and_weighting(self):
        data = candles([100] * 104 + [99, 102])
        anchor = (NOW - timedelta(minutes=10)).isoformat()
        result = evaluate_setup(data, NOW, symbol="TEST", mode="vwap_flip", session_start=anchor)
        self.assertTrue(result["ready"])
        self.assertEqual(result["vwap"], 100.5)
        self.assertEqual(result["vwap_flip"], "bullish")
        data[-1]["volume"] = 30
        self.assertEqual(evaluate_setup(data, NOW, symbol="TEST", mode="vwap_flip", session_start=anchor)["vwap"], 101.25)

    def test_bad_volume_and_incomplete_anchor(self):
        for fault in ("tick", "zero", "missing_anchor", "incomplete"):
            data = candles([100] * 104 + [99, 102])
            anchor = (NOW - timedelta(minutes=10)).isoformat()
            if fault == "tick": data[-1]["volume_type"] = "tick"
            if fault == "zero": data[-1]["volume"] = 0
            if fault == "missing_anchor": anchor = None
            if fault == "incomplete": anchor = (NOW - timedelta(days=2)).isoformat()
            self.assertFalse(evaluate_setup(data, NOW, symbol="TEST", mode="vwap_flip", session_start=anchor)["ready"])

    def test_pullback_bull_bear_and_no_touch(self):
        for direction in (1, -1):
            data = candles([100 + direction * i / 10 for i in range(106)])
            data[-1]["low"] -= 2
            data[-1]["high"] += 2
            result = evaluate_setup(data, NOW, symbol="TEST", mode="ema9_rollback")
            self.assertEqual(result["ema9_rollback"], "bullish" if direction == 1 else "bearish")
        data = candles([100 + i / 10 for i in range(106)])
        data[-1]["low"] = data[-1]["close"]
        self.assertEqual(evaluate_setup(data, NOW, symbol="TEST", mode="ema9_rollback")["ema9_rollback"], "none")

    def test_entry_and_exit_integration(self):
        for mode in ("vwap_flip", "ema9_rollback"):
            data = snapshot()
            candles_ = candles([100] * 104 + [99, 102]) if mode == "vwap_flip" else candles([100 + i / 10 for i in range(106)])
            data.update(signal_bars=candles_, signal_symbol="TEST", signal_session_start=(NOW - timedelta(minutes=10)).isoformat())
            state, event = step(initial_state(), data, NOW, entry_signal=mode)
            self.assertEqual(event["action"], "PAPER_ENTRY")
            later = NOW + timedelta(minutes=10)
            self.assertEqual(step(state, snapshot(later), later, entry_signal=mode)[1]["action"], "STOP_LOSS")
