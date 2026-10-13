import json
import unittest
from pathlib import Path
from research_context import lookup

class ContextTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(Path(__file__).with_name('market_200_sessions.json').read_text())
    def test_complete_watchlist(self):
        self.assertEqual(len(self.data['results']),18)
        for r in self.data['results']:
            c=lookup(self.data,r['symbol'],'2026-10-12')
            self.assertEqual(c['status'],'ok')
            self.assertFalse(c['authorizes_trade'])
            self.assertEqual(len(c['closest_co_movers']),3)
    def test_stale_and_no_proxy(self):
        self.assertEqual(lookup(self.data,'SPY','2026-10-13')['status'],'stale_context')
        self.assertEqual(lookup(self.data,'NDX','2026-10-12')['status'],'missing_or_duplicate_symbol')
    def test_nonfinite(self):
        self.data['results'][0]['return_pct']=float('nan')
        with self.assertRaises(ValueError):
            lookup(self.data,self.data['results'][0]['symbol'],'2026-10-12')

if __name__=='__main__': unittest.main()
