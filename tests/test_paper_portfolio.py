"""Shared-portfolio restart, concurrency and failure tests; synthetic data only."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from credit_paper import configured_risk
from ndx_paper import step, initial_state
from paper_pipeline import build_snapshot
from paper_portfolio import (apply_observation, locked_portfolio, reconcile_exports,
                             validate_plan, LIMITS, PLAN_FIELDS)
from paper_replay import new_archive, replay
from test_credit_paper import snapshot, config
from test_paper_pipeline import bundle, NOW


def inputs(strategy='iron_condor', now=NOW):
    b=bundle(now); b['options']=snapshot(strategy,now)
    return b,build_snapshot(b,now,allow_fixtures=True)


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.db=self.root/'fixture-portfolio.sqlite3'

    def apply(self,strategy,name,now=NOW,initializing=False,s=None):
        path=self.root/name
        a=json.loads(path.read_text()) if path.exists() else new_archive(strategy)
        s=s or inputs(strategy,now)[1]
        return apply_observation(self.db,path,a,s,now,initializing=initializing)

    def test_verified_limits(self):
        risk=configured_risk()
        self.assertEqual({k:risk[k] for k in LIMITS},LIMITS)

    def test_joint_position_and_trade_limit_survive_restart_and_exit(self):
        _,state,report=self.apply('iron_condor','condor.json',initializing=True)
        self.assertEqual(state['events'][-1]['action'],'PAPER_ENTRY')
        self.assertEqual(report['shared_portfolio']['open_positions'],1)
        self.assertEqual(report['shared_portfolio']['cash'],'3298.00')
        _,state,_=self.apply('iron_butterfly','butterfly.json',NOW+timedelta(seconds=1),True)
        self.assertEqual(state['events'][-1]['action'],'NO_TRADE')
        later=NOW+timedelta(minutes=10); s=inputs(now=later)[1]
        for q in s['quotes']:
            if q['instrument_id'].startswith('short'): q['ask_price']='3.4'
        _,state,_=self.apply('iron_condor','condor.json',later,s=s)
        self.assertEqual(state['events'][-1]['action'],'STOP_LOSS')
        _,state,report=self.apply('iron_butterfly','butterfly.json',later+timedelta(seconds=1))
        self.assertEqual(state['events'][-1]['action'],'NO_TRADE')
        self.assertEqual(report['shared_portfolio']['trades_today'],1)
        self.assertEqual(report['shared_portfolio']['daily_pnl'],'-304.00')
        self.assertEqual(report['shared_portfolio']['cash'],'2696.00')

    def test_unresolved_previous_day_position_blocks_new_strategy(self):
        self.apply('iron_condor','condor.json',initializing=True)
        later=NOW+timedelta(days=1); s=inputs('iron_butterfly',later)[1]
        for i in s['instruments']: i['expiration_date']='2026-10-16'
        _,state,report=self.apply('iron_butterfly','butterfly.json',later,True,s=s)
        self.assertEqual(report['shared_portfolio']['trades_today'],0)
        self.assertEqual(report['shared_portfolio']['open_positions'],1)
        self.assertEqual(state['events'][-1]['action'],'NO_TRADE')

    def test_shared_daily_loss_blocks_other_strategy_next_observation(self):
        self.apply('iron_condor','condor.json',initializing=True)
        now=NOW+timedelta(minutes=1); s=inputs(now=now)[1]
        for q in s['quotes']:
            if q['instrument_id'].startswith('short'): q['ask_price']='6'
        _,state,_=self.apply('iron_condor','condor.json',now,s=s)
        self.assertEqual(state['events'][-1]['net_pnl'],'-824.00')
        _,state,report=self.apply('iron_butterfly','butterfly.json',now+timedelta(seconds=1),True)
        self.assertEqual(state['events'][-1]['action'],'NO_TRADE')
        self.assertEqual(report['shared_portfolio']['daily_pnl'],'-824.00')

    def test_trade_risk_and_aggregate_risk_boundaries(self):
        s=inputs()[1]
        s['portfolio_context']=dict(open_positions=0,open_risk='546',daily_pnl='0',trades_today=0,cash='3000')
        self.assertEqual(step(initial_state(),s,NOW,**config())[1]['action'],'PAPER_ENTRY')
        s['portfolio_context']['open_risk']='546.01'
        self.assertEqual(step(initial_state(),s,NOW,**config())[1]['action'],'NO_TRADE')
        a=new_archive('iron_condor'); a['config']['risk']['max_risk_per_trade']=501
        with self.assertRaises(ValueError):
            apply_observation(self.db,self.root/'bad.json',a,s,NOW,initializing=True)
        self.assertFalse((self.root/'bad.json').exists())
        s['portfolio_context'].update(open_risk='0',daily_pnl='-749.99')
        self.assertEqual(step(initial_state(),s,NOW,**config())[1]['action'],'PAPER_ENTRY')
        s['portfolio_context']['daily_pnl']='-750'
        self.assertEqual(step(initial_state(),s,NOW,**config())[1]['action'],'NO_TRADE')

    def test_crash_after_canonical_commit_recovers_once(self):
        path=self.root/'condor.json'; s=inputs()[1]
        with patch('paper_portfolio.export',side_effect=OSError('simulated interruption')):
            with self.assertRaises(OSError):
                apply_observation(self.db,path,new_archive('iron_condor'),s,NOW,initializing=True)
        self.assertFalse(path.exists())
        with locked_portfolio(self.db) as db: reconcile_exports(db)
        state,_=replay(json.loads(path.read_text()))
        self.assertEqual(sum(e['action']=='PAPER_ENTRY' for e in state['events']),1)
        _,other,_=self.apply('iron_butterfly','butterfly.json',NOW+timedelta(seconds=1),True)
        self.assertEqual(other['events'][-1]['action'],'NO_TRADE')

    def test_external_edit_and_backward_observation_fail_without_reset(self):
        self.apply('iron_condor','condor.json',initializing=True)
        path=self.root/'condor.json'; data=path.read_bytes()
        with self.assertRaises(ValueError):
            self.apply('iron_butterfly','butterfly.json',NOW-timedelta(seconds=1),True)
        path.write_bytes(data+b' ')
        with self.assertRaises(ValueError):
            self.apply('iron_butterfly','butterfly.json',NOW+timedelta(seconds=1),True)
        self.assertEqual(path.read_bytes(),data+b' ')

    def test_plan_missing_rules_and_fixed_ids(self):
        plan=dict(mode='explicit_contract_plan',strategy='iron_condor',legs=snapshot()['selection']['legs'])
        for field in PLAN_FIELDS:
            with self.assertRaises(ValueError): validate_plan(plan)
            plan[field]='Fixed explicit instrument IDs; see metadata'
        validate_plan(plan)
        self.apply('iron_condor','condor.json',initializing=True)
        s=inputs('iron_butterfly',NOW+timedelta(seconds=1))[1]
        bad=deepcopy(plan); bad['legs']['long_put']='other'
        with self.assertRaises(ValueError):
            apply_observation(self.db,self.root/'other.json',new_archive('iron_butterfly'),s,NOW+timedelta(seconds=1),initializing=True,plan=bad)

    def test_fixture_observed_separation_and_unregistered_archive_preservation(self):
        self.apply('iron_condor','condor.json',initializing=True)
        s=inputs('iron_butterfly',NOW+timedelta(seconds=1))[1]
        s['provenance']['source']['kind']='observed'
        with self.assertRaises(ValueError):
            apply_observation(self.db,self.root/'other.json',new_archive('iron_butterfly'),s,NOW+timedelta(seconds=1),initializing=True)
        from paper_replay import observe
        a=observe(new_archive('iron_butterfly'),inputs('iron_butterfly')[1],NOW)
        path=self.root/'unmanaged.json'; path.write_text(json.dumps(a)); before=path.read_bytes()
        with self.assertRaises(ValueError):
            apply_observation(self.db,path,a,inputs('iron_butterfly',NOW+timedelta(seconds=1))[1],NOW+timedelta(seconds=1))
        self.assertEqual(before,path.read_bytes())

    def test_simultaneous_cli_runs_cannot_open_two_positions(self):
        root=Path(__file__).resolve().parents[1]
        env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
        processes=[]
        for strategy in ('iron_condor','iron_butterfly'):
            b,_=inputs(strategy); source=self.root/(strategy+'-fixture.json'); source.write_text(json.dumps(b))
            cmd=[sys.executable,str(root/'paper_pipeline.py'),str(source),'--archive',str(self.root/(strategy+'.json')),
                 '--portfolio',str(self.db),'--strategy',strategy,'--historical','--allow-fixtures','--init']
            processes.append(subprocess.Popen(cmd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE))
        actions=[]
        for p in processes:
            stdout,stderr=p.communicate(timeout=30)
            self.assertEqual(p.returncode,0,stderr)
            actions.append(json.loads(stdout)['action'])
        self.assertCountEqual(actions,['PAPER_ENTRY','NO_TRADE'])
        with locked_portfolio(self.db) as db:
            archives=reconcile_exports(db)
        self.assertEqual(sum(replay(a)[0]['position'] is not None for a in archives.values()),1)
