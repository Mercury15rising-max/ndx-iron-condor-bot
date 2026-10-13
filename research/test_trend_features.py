import tempfile
import unittest
from datetime import date, timedelta
from trend_features import analyze, collect

def entry(n=220):
    return dict(symbol='TEST', interval='day', bounds='regular', bars=[
        dict(begins_at=(date(2025, 1, 1)+timedelta(days=i)).isoformat()+'T00:00:00Z',
             close_price=str(i+1)) for i in range(n)])

class Trends(unittest.TestCase):
    def test_numeric_windows(self):
        e=entry(); r=analyze(e,e['bars'][-1]['begins_at'][:10])
        self.assertEqual(r['sma200'],120.5)
        self.assertEqual(r['sma50'],195.5)
        self.assertAlmostEqual(r['slope200_20_pct'],(120.5/100.5-1)*100)
        self.assertEqual(r['regime'],'bullish')

    def test_exclusions_and_short_history(self):
        e=entry(221); cutoff=e['bars'][219]['begins_at'][:10]
        e['bars'][0]['interpolated']=True
        r=analyze(e,cutoff)
        self.assertEqual(r['observations'],219)
        self.assertEqual(r['excluded_bars'],2)
        self.assertEqual(r['status'],'insufficient_history')
        self.assertIsNone(r['slope200_20_pct'])

    def test_stale_duplicate_bad_close(self):
        e=entry()
        self.assertEqual(analyze(e,'2026-01-01')['regime'],'unknown')
        e['bars'].append(e['bars'][0])
        with self.assertRaises(ValueError): analyze(e,'2026-01-01')
        e=entry(); e['bars'][0]['close_price']='NaN'
        with self.assertRaises(ValueError): analyze(e,'2026-01-01')

    def test_persistence_and_missing_symbol(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path=d+'/trends.db'; payload=dict(adjustment_type='split',results=[entry()])
            for _ in range(2):
                rows=collect(payload,['TEST','MISSING'],'2025-08-08',path)
            self.assertEqual(rows[1]['status'],'data_error')
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM trend_snapshots').fetchone()[0],2)

if __name__=='__main__': unittest.main()
