import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from test_paper_strategy_lab import NOW
from paper_pricing import PricedPaperLedger

def quotes():
    return [dict(instrument_id=str(i),symbol='TEST',expiration='2026-10-14',
        strike=k,option_type=t,bid=b,ask=b+.01,delta=d,multiplier=100,
        quote_timestamp=NOW.isoformat(),bid_size=5,ask_size=5,volume=100,open_interest=100)
        for i,(k,t,b,d) in enumerate([(99,'put',1,-.05),(100,'put',1.45,-.12),
                                    (101,'call',1.45,.12),(102,'call',1,.05)])]

class PricingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=str(Path(self.tmp.name)/'paper.sqlite')
        self.ledger=PricedPaperLedger(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_priced_roundtrip_restart_and_limits(self):
        q=quotes();r=self.ledger.enter('p1',q,NOW,fee=1,slippage=0)
        self.assertEqual(r['risk'],20)
        self.assertEqual(r['entry_cash'],84)
        self.ledger=PricedPaperLedger(self.path)
        q[1]['bid']=q[2]['bid']=1.25;q[1]['ask']=q[2]['ask']=1.26
        signal=self.ledger.exit_signal('p1',q,NOW,profit_target=20,loss_limit=20)
        self.assertEqual(signal['signal'],'take_profit')
        self.assertEqual(signal['net_pnl'],28)
        self.ledger.exit('p1',q,NOW)
        with self.assertRaises(ValueError):self.ledger.exit('p1',q,NOW)
        s,reasons=self.ledger.check(20,NOW.isoformat())
        self.assertEqual(s['balance'],302800)
        self.assertIn('position_or_trade_limit',reasons)
    def test_bad_quotes_cannot_close(self):
        q=quotes();self.ledger.enter('p1',q,NOW,slippage=0)
        with self.assertRaises(ValueError):self.ledger.exit('p1',q,NOW+timedelta(seconds=31))
        q[0]['instrument_id']='wrong'
        with self.assertRaises(ValueError):self.ledger.exit('p1',q,NOW)
        self.assertEqual(self.ledger.check(1,NOW.isoformat())[0]['open_positions'],1)
    def test_risk_and_size(self):
        q=quotes();q[0]['ask_size']=0
        with self.assertRaises(ValueError):self.ledger.enter('p1',q,NOW,slippage=0)
        self.assertEqual(self.ledger.check(1,NOW.isoformat())[0]['open_positions'],0)
        q=quotes();q[1]['bid']=q[2]['bid']=1.2;q[1]['ask']=q[2]['ask']=1.21
        with self.assertRaises(ValueError):self.ledger.enter('p2',q,NOW,slippage=0)

if __name__=='__main__':unittest.main()
