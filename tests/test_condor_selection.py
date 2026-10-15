"""Synthetic selector fixtures only; never actual-market plan creation."""
from copy import deepcopy
from datetime import timedelta
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from condor_selection import RULESET, select_condor, make_plan
from ndx_paper import initial_state, step
from paper_replay import new_archive, observe, replay
from paper_portfolio import apply_observation
from test_credit_paper import snapshot
from test_ndx_paper import NOW
from test_paper_pipeline import bundle
from paper_pipeline import build_snapshot


def data():
    s=snapshot()
    for i,strike in zip(s['instruments'],('75','100','150','175')):
        i['strike_price']=strike
    for q in s['quotes']:
        short=q['instrument_id'].startswith('short')
        q.update(bid_price='11.1' if short else '0.8',ask_price='11.2' if short else '1',
                 delta='-0.12' if q['instrument_id']=='short_put' else '0.12' if short else '0.01')
    s.pop('selection')
    return s


def add(s,id,kind,strike,delta,expiry='2026-10-15'):
    i=deepcopy(s['instruments'][0]); i.update(id=id,type=kind,strike_price=str(strike),expiration_date=expiry)
    q=deepcopy(s['quotes'][0]); q.update(instrument_id=id,delta=str(delta))
    s['instruments'].append(i); s['quotes'].append(q)


class CondorSelectionTests(unittest.TestCase):
    def test_exact_symmetric_wings_and_original_ids(self):
        s=data(); result=select_condor(s,NOW)
        self.assertEqual(result,dict(strategy='iron_condor',legs={r:r for r in ('long_put','short_put','short_call','long_call')}))
        state,event=step(initial_state(),s,NOW,**new_archive('iron_condor',selection_rules=RULESET)['config'])
        self.assertEqual(event['action'],'PAPER_ENTRY')
        self.assertEqual(state['position']['max_loss'],'484.00')

    def test_earliest_eligible_expiry_excludes_zero_and_over_seven_days_and_am(self):
        s=data()
        for expiry in ('2026-10-14','2026-10-16','2026-10-22'):
            for i,q in zip(data()['instruments'],data()['quotes']):
                i.update(id=i['id']+expiry,expiration_date=expiry)
                q['instrument_id']=i['id']; s['instruments'].append(i); s['quotes'].append(q)
        self.assertEqual(select_condor(s,NOW)['legs']['short_put'],'short_put')
        s['chains'][0]['settle_on_open']=True
        with self.assertRaises(ValueError): select_condor(s,NOW)

    def test_seven_day_boundary(self):
        s=data()
        for i in s['instruments']: i['expiration_date']='2026-10-21'
        self.assertEqual(select_condor(s,NOW)['strategy'],'iron_condor')
        for i in s['instruments']: i['expiration_date']='2026-10-22'
        with self.assertRaises(ValueError): select_condor(s,NOW)

    def test_short_delta_inclusive_boundaries_and_outside_rejection(self):
        for delta in ('0.10','0.15','-0.10','-0.15'):
            s=data()
            for q in s['quotes']:
                if q['instrument_id'].startswith('short'): q['delta']=delta
            self.assertEqual(select_condor(s,NOW)['strategy'],'iron_condor')
        for delta in ('0.0999','0.1501','NaN'):
            s=data(); s['quotes'][1]['delta']=delta
            with self.assertRaises(ValueError): select_condor(s,NOW)

    def test_highest_put_lowest_call_and_provider_order_independence(self):
        s=data()
        for id,kind,strike,delta in (('put105','put',105,-.14),('wing80','put',80,-.01),
                                    ('call145','call',145,.10),('wing170','call',170,.01)):
            add(s,id,kind,strike,delta)
        expected=select_condor(s,NOW)
        self.assertEqual(expected['legs'],dict(long_put='wing80',short_put='put105',short_call='call145',long_call='wing170'))
        rng=random.Random(0)
        for _ in range(20):
            shuffled=deepcopy(s)
            for name in ('chains','instruments','quotes'): rng.shuffle(shuffled[name])
            self.assertEqual(select_condor(shuffled,NOW),expected)

    def test_no_nearest_wing_or_later_expiration_substitution(self):
        s=data(); s['instruments'][0]['strike_price']='74'
        with self.assertRaises(ValueError): select_condor(s,NOW)
        for i,q in zip(data()['instruments'],data()['quotes']):
            i.update(id=i['id']+'later',expiration_date='2026-10-16')
            q['instrument_id']=i['id']; s['instruments'].append(i); s['quotes'].append(q)
        state,e=step(initial_state(),s,NOW,**new_archive('iron_condor',selection_rules=RULESET)['config'])
        self.assertEqual(e['action'],'NO_TRADE'); self.assertIsNone(state['position'])

    def test_duplicate_ids_ambiguous_contracts_and_multiple_chains_rejected(self):
        for problem in ('id','ambiguous','chains'):
            s=data()
            if problem=='id': s['instruments'].append(deepcopy(s['instruments'][0]))
            elif problem=='ambiguous': add(s,'different_id','put',100,-.12)
            else:
                c=deepcopy(s['chains'][0]); c['id']='other'; s['chains'].append(c)
                i=deepcopy(s['instruments'][0]); i.update(id='other_leg',chain_id='other'); s['instruments'].append(i)
            with self.subTest(problem=problem),self.assertRaises(ValueError): select_condor(s,NOW)

    def test_missing_or_stale_selected_leg_records_no_trade(self):
        for index in range(4):
            for problem in ('missing','stale','size','future'):
                s=data()
                if problem=='missing': s['quotes'].pop(index)
                elif problem=='stale': s['quotes'][index]['updated_at']=(NOW-timedelta(seconds=61)).isoformat()
                elif problem=='future': s['quotes'][index]['updated_at']=(NOW+timedelta(seconds=1)).isoformat()
                else: s['quotes'][index]['bid_size']=0
                _,e=step(initial_state(),s,NOW,**new_archive('iron_condor',selection_rules=RULESET)['config'])
                self.assertEqual(e['action'],'NO_TRADE')

    def test_fee_inclusive_500_boundary_and_shared_limit_rejections(self):
        c=new_archive('iron_condor',selection_rules=RULESET)['config']
        s=data()
        for q in s['quotes']:
            if q['instrument_id'].startswith('short'): q['bid_price']='11.02'
        self.assertEqual(step(initial_state(),s,NOW,**c)[1]['action'],'PAPER_ENTRY')
        s['quotes'][1]['bid_price']='11.0199'
        self.assertEqual(step(initial_state(),s,NOW,**c)[1]['action'],'NO_TRADE')
        for field,value in (('open_positions',1),('trades_today',1),('daily_pnl','-750'),('open_risk','300')):
            s=data(); context=dict(open_positions=0,trades_today=0,daily_pnl='0',open_risk='0',cash='3000')
            context[field]=value; s['portfolio_context']=context
            self.assertEqual(step(initial_state(),s,NOW,**c)[1]['action'],'NO_TRADE')

    def test_fixed_condor_rejects_butterfly_and_fixture_plan_creation(self):
        with self.assertRaises(ValueError): new_archive('iron_butterfly',selection_rules=RULESET)
        s=data(); s['provenance']=dict(source=dict(kind='fixture',name='synthetic'))
        with self.assertRaises(ValueError): make_plan(s,NOW)

    def test_no_trade_and_whole_position_exit_replay(self):
        archive=new_archive('iron_condor',selection_rules=RULESET)
        s=data(); s['instruments'][0]['strike_price']='74'
        archive=observe(archive,s,NOW)
        self.assertEqual(replay(archive)[0]['events'][-1]['action'],'NO_TRADE')
        now=NOW+timedelta(seconds=1); s=data()
        s['session_observed_at']=now.isoformat()
        for q in s['quotes']: q['updated_at']=now.isoformat()
        archive=observe(archive,s,now)
        later=NOW.replace(hour=19,minute=30); s=data(); s['instruments']=[]; s['chains']=[]
        s['session_observed_at']=later.isoformat()
        for q in s['quotes']: q['updated_at']=later.isoformat()
        archive=observe(archive,s,later)
        state,report=replay(archive)
        self.assertEqual(report['completed_trades'],1); self.assertIsNone(state['position'])

    def test_cli_refuses_fixture_as_actual_plan_without_creating_file(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fixture.json'; plan=Path(tmp)/'condor-selection-plan.json'
            b=bundle(); b['options']=data(); source.write_text(json.dumps(b))
            env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
            r=subprocess.run([sys.executable,str(root/'condor_selection.py'),str(source),'--plan',str(plan),'--historical'],env=env,capture_output=True)
            self.assertNotEqual(r.returncode,0); self.assertFalse(plan.exists())

    def test_pipeline_persists_missing_wing_no_trade_then_rule_selected_entry(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fixture.json'; archive=Path(tmp)/'fixed-condor-fixture.json'
            env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
            cmd=[sys.executable,str(root/'paper_pipeline.py'),str(source),'--archive',str(archive),
                 '--strategy','iron_condor','--selection-rules',RULESET,'--historical','--allow-fixtures']
            for index,now in enumerate((NOW,NOW+timedelta(seconds=1))):
                b=bundle(now); b['options']=data(); b['options']['session_observed_at']=now.isoformat()
                for q in b['options']['quotes']: q['updated_at']=now.isoformat()
                if not index: b['options']['instruments'][0]['strike_price']='74'
                source.write_text(json.dumps(b))
                result=subprocess.run(cmd+(['--init'] if not index else []),env=env,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(json.loads(result.stdout)['action'],'NO_TRADE' if not index else 'PAPER_ENTRY')
            state,report=replay(json.loads(archive.read_text()))
            self.assertEqual([e['action'] for e in state['events']],['NO_TRADE','PAPER_ENTRY'])
            self.assertEqual(state['position']['legs']['long_put']['id'],'long_put')
            self.assertEqual(report['completed_trades'],0)
