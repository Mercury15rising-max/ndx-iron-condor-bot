import unittest
from datetime import datetime, timezone, timedelta
from test_spxw_paper import snapshot
from test_ema_signals import bars
from ndx_paper import initial_state, step
from exchange_session import bounds

NOW = datetime(2026, 10, 14, 17, 0, tzinfo=timezone.utc)


def data(now=NOW):
    s = snapshot(now)
    for c in s['chains']:
        c['symbol'] = 'NDXP'
    for i in s['instruments']:
        i['chain_symbol'] = 'NDXP'
    candles = bars()
    # Synthetic prices on genuine session boundaries, never market observations.
    ends = []
    day = now.date() - timedelta(days=10)
    while day <= now.date():
        hours = bounds(day)
        if hours:
            end = hours[0] + timedelta(minutes=5)
            while end <= min(hours[1], now):
                ends.append(end)
                end += timedelta(minutes=5)
        day += timedelta(days=1)
    ends = ends[-len(candles):]
    for b, end in zip(candles, ends):
        b['symbol'] = 'QQQ'
        b['close_time'] = end.isoformat()
    s.update(signal_symbol='QQQ', signal_bars=candles)
    return s


class NDXTests(unittest.TestCase):
    def test_deterministic_entry(self):
        a = step(initial_state(), data(), NOW)
        self.assertEqual(a, step(initial_state(), data(), NOW))
        self.assertEqual(a[1]['action'], 'PAPER_ENTRY')
        self.assertEqual(a[0]['position']['long']['chain_symbol'], 'NDXP')

    def test_wrong_proxy_and_outside_window(self):
        s = data(); s['signal_symbol'] = 'NDX'
        self.assertEqual(step(initial_state(), s, NOW)[1]['action'], 'NO_TRADE')
        later = NOW.replace(hour=19)
        self.assertEqual(step(initial_state(), data(later), later)[1]['action'], 'NO_TRADE')

    def test_stop_and_one_entry_daily(self):
        state, _ = step(initial_state(), data(), NOW)
        later = NOW + timedelta(minutes=10)
        state, event = step(state, data(later), later)
        self.assertEqual(event['action'], 'STOP_LOSS')
        self.assertEqual(step(state, data(later + timedelta(seconds=1)), later + timedelta(seconds=1))[1]['reason'], 'One paper entry per day')

    def test_reject_spx_ledger_and_stale_quotes(self):
        from spxw_paper import initial_state as spx_state
        with self.assertRaises(ValueError): step(spx_state(), data(), NOW)
        self.assertEqual(step(initial_state(), data(), NOW + timedelta(seconds=61))[1]['action'], 'UNAVAILABLE')
