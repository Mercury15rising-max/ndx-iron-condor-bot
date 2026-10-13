import tempfile
import unittest
from paper_ledger import PaperLedger

class LedgerTests(unittest.TestCase):
    def test_persistence_and_limits(self):
        with tempfile.TemporaryDirectory() as d:
            p=d+'/account.db'; ledger=PaperLedger(p)
            ledger.open_simulation('a',30,'2026-10-13T16:00:00Z','synthetic test')
            self.assertIn('position_or_trade_limit',PaperLedger(p).check(1,'2026-10-13T17:00:00Z')[1])
            ledger.close_simulation('a',-30,'2026-10-14T15:00:00Z','synthetic loss')
            state,reasons=ledger.check(29,'2026-10-14T16:00:00Z')
            self.assertEqual(state['balance'],297000)
            self.assertEqual(state['daily_loss'],3000)
            self.assertEqual(state['risk_cap'],2970)
            self.assertEqual(reasons,[])
            ledger.open_simulation('b',29,'2026-10-14T16:00:00Z','synthetic test')
            ledger.close_simulation('b',-29,'2026-10-14T17:00:00Z','synthetic loss')
            self.assertIn('daily_loss_budget',ledger.check(1,'2026-10-14T18:00:00Z')[1])
            state,reasons=ledger.check(20,'2026-10-15T16:00:00Z')
            self.assertEqual(state['daily_loss'],0)
            self.assertEqual(reasons,[])
            with self.assertRaises(ValueError): ledger.close_simulation('b',0,'2026-10-15T17:00:00Z','duplicate')
            with self.assertRaises(ValueError): ledger.check(1,'2026-10-13T16:00:00Z')

    def test_no_automatic_fill(self):
        with tempfile.TemporaryDirectory() as d:
            l=PaperLedger(d+'/a.db')
            r=l.gate(dict(max_loss_after_costs=31,reasons=[],status='research_candidate',filled=False),'2026-10-13T16:00:00Z')
            self.assertEqual(r['status'],'rejected')
            self.assertFalse(r['filled'])
            self.assertEqual(l.check(20,'2026-10-13T16:00:00Z')[0]['open_positions'],0)

if __name__=='__main__': unittest.main()
