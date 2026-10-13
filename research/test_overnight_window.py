import unittest
from datetime import datetime,timezone
from test_paper_strategy_lab import fixture
from paper_strategy_lab import evaluate

class NightTests(unittest.TestCase):
    def check_at(self,t,symbol='SPXW',enabled=True):
        now=datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        q=fixture()
        for leg in q:leg.update(symbol=symbol,quote_timestamp=now.isoformat())
        return evaluate(q,now,overnight_test=enabled)['reasons']
    def test_boundaries_and_default(self):
        for t in ['2026-10-14T00:14:59','2026-10-14T00:45:00','2026-10-15T00:15:00']:
            self.assertIn('outside_entry_window',self.check_at(t))
        self.assertNotIn('outside_entry_window',self.check_at('2026-10-14T00:15:00'))
        self.assertIn('outside_entry_window',self.check_at('2026-10-14T00:15:00',enabled=False))
        self.assertIn('outside_entry_window',self.check_at('2026-10-14T00:15:00',symbol='NDXP'))
    def test_risk_survives(self):
        self.assertIn('per_trade_risk',self.check_at('2026-10-14T00:15:00'))

if __name__=='__main__':unittest.main()
