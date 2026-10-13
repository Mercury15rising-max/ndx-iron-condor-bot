"""Offline adapter/evaluator/ledger integration; synthetic quotes, no broker calls."""
import tempfile
import unittest
from pathlib import Path
from test_paper_strategy_lab import fixture, NOW
from supported_session import make_snapshot
from paper_strategy_lab import evaluate
from paper_ledger import PaperLedger

class ReadinessTests(unittest.TestCase):
    def test_nonfinite_costs_and_liquidity(self):
        for value in (float('nan'),float('inf'),-1):
            with self.assertRaises(ValueError): evaluate(fixture(),NOW,fee=value)
            with self.assertRaises(ValueError): evaluate(fixture(),NOW,slippage=value)
        q=fixture();q[0]['volume']=float('nan');q[1]['open_interest']=float('inf')
        reasons=evaluate(q,NOW)['reasons']
        self.assertIn('volume_below_10',reasons)
        self.assertIn('open_interest_below_50',reasons)

    def test_adapter_to_risk_ledger(self):
        contracts=[];quotes=[]
        for i,q in enumerate(fixture()):
            contracts.append(dict(q,instrument_id=str(i),multiplier=100))
            quotes.append({'quote':dict(instrument_id=str(i),bid_price=q['bid'],
                ask_price=q['ask'],delta=q['delta'],updated_at=q['quote_timestamp'],
                volume=q['volume'],open_interest=q['open_interest'])})
        snapshot=make_snapshot(contracts,{'data':{'results':quotes}})
        self.assertFalse(snapshot['live_execution_enabled'])
        # Use fixture timestamp for reproducible replay, not a claim of fresh quotes.
        candidate=evaluate(snapshot['quotes'],NOW)
        with tempfile.TemporaryDirectory() as tmp:
            ledger=PaperLedger(str(Path(tmp)/'paper.sqlite'))
            gated=ledger.gate(candidate,NOW.isoformat())
            self.assertEqual(gated['status'],'rejected')
            self.assertIn('per_trade_risk',gated['reasons'])
            self.assertFalse(gated['filled'])
            self.assertEqual(gated['paper_account_cents']['open_positions'],0)
        with self.assertRaises(ValueError):
            make_snapshot(contracts,{'data':{'results':quotes[:-1]}})
        with self.assertRaises(ValueError):
            make_snapshot(contracts,{'data':{'results':quotes+quotes[:1]}})

if __name__=='__main__': unittest.main()
