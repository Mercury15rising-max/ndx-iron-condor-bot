import unittest
from copy import deepcopy
from datetime import datetime, timezone
from paper_strategy_lab import evaluate, compare

NOW = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)

def fixture():
    return [dict(symbol='NDXP', expiration='2026-10-14', strike=k, option_type=t,
                 bid=b, ask=b+.2, delta=d, quote_timestamp=NOW.isoformat(), open_interest=100, volume=30)
            for k,t,b,d in [(90,'put',1,-.05),(95,'put',2,-.12),(105,'call',2,.12),(110,'call',1,.05)]]

class Tests(unittest.TestCase):
    def test_conservative_costs(self):
        r=evaluate(fixture(), NOW)
        self.assertAlmostEqual(r['conservative_credit_points'],1.2)
        self.assertEqual(r['max_loss_after_costs'],388)
        self.assertFalse(r['filled'])
        self.assertEqual(r['status'],'rejected')
        self.assertIn('per_trade_risk',r['reasons'])
        self.assertEqual(r['risk_cap'],30)
        self.assertEqual(r['paper_balance'],3000)

    def test_rejects_stale_and_liquidity(self):
        q=fixture(); q[0]['quote_timestamp']='2026-10-13T15:59:00Z';q[0]['volume']=0
        r=evaluate(q,NOW)
        self.assertIn('stale_or_future_quote',r['reasons'])
        self.assertIn('volume_below_10',r['reasons'])

    def test_rejects_impossible_credit(self):
        q=fixture();q[1]['bid']=10;q[1]['ask']=10.2
        self.assertIn('inconsistent_package_pricing',evaluate(q,NOW)['reasons'])

    def test_exact_wings_required(self):
        r=compare(fixture(),NOW,widths=(25,))
        self.assertEqual(r[0]['reasons'],['missing_exact_wings'])

    def test_mixed_expiry_fails(self):
        q=fixture();q[0]['expiration']='2026-10-15'
        with self.assertRaises(ValueError):evaluate(q,NOW)

    def test_butterfly(self):
        q=fixture();q[1]['strike']=100;q[2]['strike']=100
        r=evaluate(q,NOW)
        self.assertEqual(r['strategy'],'iron_butterfly')
        self.assertIn('per_trade_risk',r['reasons'])

if __name__ == '__main__':unittest.main()
