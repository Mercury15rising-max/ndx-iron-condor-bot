import unittest
from datetime import datetime,timedelta,timezone
from ema_signals import evaluate_ema, evaluate_setup
from session_bars import normalize_robinhood


def fixture():
    sessions=[{'open':'2026-10-09T13:30:00Z','close':'2026-10-09T20:00:00Z'},
              {'open':'2026-10-12T13:30:00Z','close':'2026-10-12T20:00:00Z'}]
    calendar=dict(complete=True, source='test fixture',coverage_start='2026-10-09T00:00:00Z',coverage_end='2026-10-13T00:00:00Z',sessions=sessions)
    bars=[]
    for session in sessions:
        t=datetime.fromisoformat(session['open'].replace('Z','+00:00'))+timedelta(minutes=5)
        end=datetime.fromisoformat(session['close'].replace('Z','+00:00'))
        while t<=end:
            bars.append(dict(symbol='TEST',timeframe_seconds=300,close_time=t.isoformat(),closed=True,close=100,high=101,low=99,volume=10,volume_type='trade'))
            t+=timedelta(minutes=5)
    return bars,calendar,datetime(2026,10,12,20,tzinfo=timezone.utc)


class SessionTests(unittest.TestCase):
    def test_weekend_history_valid_without_fill(self):
        bars,cal,now=fixture()
        self.assertFalse(evaluate_ema(bars,now,symbol='TEST')['ready'])
        r=evaluate_ema(bars,now,symbol='TEST',session_calendar=cal)
        self.assertTrue(r['ready']);self.assertEqual(r['closed_bars'],156)
        self.assertEqual(r['ema21'],100)

    def test_missing_open_midday_or_close_rejected(self):
        for index in (30,77,78):
            bars,cal,now=fixture();bars.pop(index)
            self.assertFalse(evaluate_ema(bars,now,symbol='TEST',session_calendar=cal)['ready'])

    def test_incomplete_calendar_and_stale_rejected(self):
        bars,cal,now=fixture();cal['complete']=False
        self.assertFalse(evaluate_ema(bars,now,symbol='TEST',session_calendar=cal)['ready'])
        cal['complete']=True
        self.assertFalse(evaluate_ema(bars,now+timedelta(minutes=6),symbol='TEST',session_calendar=cal)['ready'])

    def test_early_close_and_holiday(self):
        bars,cal,now=fixture()
        cal['sessions'][0]['close']='2026-10-09T17:00:00Z'
        bars=[b for b in bars if not '2026-10-09' in b['close_time'] or b['close_time']<='2026-10-09T17:00:00+00:00']
        self.assertTrue(evaluate_ema(bars,now,symbol='TEST',session_calendar=cal)['ready'])

    def test_vwap_cannot_cross_session_reset(self):
        bars,cal,now=fixture()
        r=evaluate_setup(bars,now,symbol='TEST',mode='vwap_flip',session_start=cal['sessions'][0]['open'],session_calendar=cal)
        self.assertFalse(r['ready'])

    def test_left_edge_and_forming(self):
        now=datetime(2026,10,14,15,32,tzinfo=timezone.utc)
        series=dict(symbol='TEST',interval='5minute',bounds='regular',bars=[dict(begins_at='2026-10-14T15:30:00Z',close_price='100',high_price='101',low_price='99',volume=1)])
        result=normalize_robinhood(series,now)
        self.assertFalse(result[0]['closed']);self.assertEqual(result[0]['close_time'],'2026-10-14T15:35:00+00:00')

class ScanTests(unittest.TestCase):
    def test_missing_symbols_are_reported_without_trades(self):
        from paper_signal_scan import scan
        _,cal,now=fixture()
        rows=scan(dict(signal_calendar=cal,series=[]),now)
        self.assertEqual(len(rows),14)
        self.assertTrue(all('error' in r and r['execution']=='NOT_ENABLED' for r in rows))

    def test_duplicate_series_rejected(self):
        from paper_signal_scan import scan
        _,cal,now=fixture()
        with self.assertRaises(ValueError):
            scan(dict(signal_calendar=cal,series=[{'symbol':'QQQ'},{'symbol':'QQQ'}]),now)
