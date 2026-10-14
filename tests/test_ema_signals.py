import unittest
from datetime import timedelta
from copy import deepcopy

from ema_signals import crossover, ema, evaluate_ema
from spxw_paper import initial_state, step
from test_spxw_paper import NOW, snapshot


def bars(prices=None):
    prices = prices or ([100.0] * 105 + [110.0])
    return [{"symbol": "TEST", "timeframe_seconds": 300, "close": price,
             "close_time": (NOW - timedelta(minutes=5 * (len(prices) - 1 - i))).isoformat(),
             "closed": True} for i, price in enumerate(prices)]


class EMASignalTests(unittest.TestCase):
    def test_known_recurrence(self):
        self.assertEqual(ema([10, 20, 30], 3), [10, 15, 22.5])

    def test_pair_cross_boundaries(self):
        self.assertEqual(crossover(1, 1, 2, 1), "bullish")
        self.assertEqual(crossover(1, 1, 0, 1), "bearish")
        self.assertEqual(crossover(0, 1, 1, 1), "none")

    def test_bull_bear_flat(self):
        for last, expected in [(110, "bullish"), (90, "bearish"), (100, "none")]:
            result = evaluate_ema(bars([100] * 105 + [last]), NOW, symbol="TEST")
            self.assertTrue(result["ready"])
            self.assertEqual(result["triple_cross"], expected)
            self.assertEqual(result["fast_cross"], expected)

    def test_alignment_does_not_repeat_cross(self):
        result = evaluate_ema(bars([100] * 104 + [110, 111]), NOW, symbol="TEST")
        self.assertEqual(result["alignment"], "bullish")
        self.assertEqual(result["triple_cross"], "none")

    def test_future_and_forming_candle_cannot_change_signal(self):
        original = evaluate_ema(bars(), NOW, symbol="TEST")
        data = bars()
        data.append({**data[-1], "close_time": (NOW + timedelta(minutes=5)).isoformat(),
                     "close": 1, "closed": False})
        self.assertEqual(evaluate_ema(data, NOW, symbol="TEST"), original)
        data[-1]["closed"] = True
        self.assertEqual(evaluate_ema(data, NOW, symbol="TEST"), original)

    def test_reject_gaps_duplicates_mixed_nan_and_interpolation(self):
        for kind in ("gap", "duplicate", "symbol", "frame", "nan", "interpolated"):
            data = bars()
            if kind == "gap":
                data.pop(50)
            elif kind == "duplicate":
                data[1]["close_time"] = data[0]["close_time"]
            elif kind == "symbol":
                data[1]["symbol"] = "OTHER"
            elif kind == "frame":
                data[1]["timeframe_seconds"] = 60
            elif kind == "nan":
                data[1]["close"] = "NaN"
            else:
                data[1]["interpolated"] = True
            with self.subTest(kind=kind):
                self.assertFalse(evaluate_ema(data, NOW, symbol="TEST")["ready"])

    def test_warmup_and_stale(self):
        self.assertFalse(evaluate_ema(bars()[:-1], NOW, symbol="TEST")["ready"])
        self.assertFalse(evaluate_ema(bars(), NOW + timedelta(seconds=301), symbol="TEST")["ready"])
        self.assertTrue(evaluate_ema(bars(), NOW + timedelta(seconds=300), symbol="TEST")["ready"])

    def test_integration_entry_and_duplicate_bar_guard(self):
        data = snapshot()
        data.update(signal_symbol="TEST", signal_bars=bars())
        state, event = step(initial_state(), data, NOW, entry_signal="triple_cross")
        self.assertEqual(event["action"], "PAPER_ENTRY")
        self.assertEqual(state["position"]["signal"]["ema8"], 100 + 20 / 9)
        # Simulate a separately closed position; retained signal ID must prevent reuse.
        state["position"] = None
        _, event = step(state, data, NOW + timedelta(seconds=1), entry_signal="triple_cross")
        self.assertEqual(event["reason"], "Crossover bar already used")

    def test_bearish_missing_and_stale_signals_block_calls(self):
        for candles in ([], bars([100] * 105 + [90])):
            data = snapshot()
            data.update(signal_symbol="TEST", signal_bars=candles)
            self.assertEqual(step(initial_state(), data, NOW, entry_signal="fast_cross")[1]["action"],
                             "NO_TRADE")

    def test_exit_runs_even_without_indicator_data(self):
        state = step(initial_state(), snapshot(), NOW)[0]
        later = NOW + timedelta(minutes=10)
        self.assertEqual(step(state, snapshot(later), later, entry_signal="triple_cross")[1]["action"],
                         "STOP_LOSS")


if __name__ == "__main__":
    unittest.main()
