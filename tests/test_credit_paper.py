"""Four-leg synthetic regression fixtures only; never observed market results."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from credit_paper import configured_risk, ROLES
from ndx_paper import initial_state, step
from paper_replay import new_archive, observe, replay, accounting
from test_ndx_paper import NOW
from test_paper_pipeline import bundle


def snapshot(strategy='iron_condor', now=NOW):
    strikes = (95,100,110,115) if strategy=='iron_condor' else (95,100,100,105)
    return dict(session_open=True, session_observed_at=now.isoformat(), complete=True,
                selection=dict(strategy=strategy, legs={r:r for r in ROLES}),
                chains=[dict(id='chain',symbol='NDXP',settle_on_open=False,
                             can_open_position=True,trade_value_multiplier='100')],
                instruments=[dict(id=r,chain_id='chain',chain_symbol='NDXP',
                                  type='put' if 'put' in r else 'call',
                                  expiration_date='2026-10-15',strike_price=str(k),
                                  state='active',tradability='tradable',trade_value_multiplier='100')
                             for r,k in zip(ROLES,strikes)],
                quotes=[dict(instrument_id=r,bid_price='2' if r.startswith('short') else '0.4',
                             ask_price='2.1' if r.startswith('short') else '0.5',
                             bid_size=1,ask_size=1,updated_at=now.isoformat()) for r in ROLES])


def config(strategy='iron_condor', fee='0.50'):
    return dict(strategy=strategy,risk=configured_risk(),fee_per_contract=fee)


class CreditPaperTests(unittest.TestCase):
    def opened(self, strategy='iron_condor'):
        state,event=step(initial_state(),snapshot(strategy),NOW,**config(strategy))
        self.assertEqual(event['action'],'PAPER_ENTRY')
        return state

    def test_entry_sides_explicit_fees_and_maximum_loss_for_both(self):
        for strategy in ('iron_condor','iron_butterfly'):
            state=self.opened(strategy); p=state['position']
            self.assertEqual(p['gross_entry_credit'],'300.0')
            self.assertEqual(p['net_entry_credit'],'298.00')
            self.assertEqual(p['entry_fee'],'2.00')
            self.assertEqual(p['exit_fee'],'2.00')
            self.assertEqual(p['max_loss'],'204.00')
            self.assertEqual(state['balance'],'3298.00')
            self.assertEqual(len(p['legs']),4)
            self.assertEqual(accounting(state)['cash'],state['balance'])

    def test_every_missing_stale_future_crossed_or_zero_size_leg_blocks_entry(self):
        for index in range(4):
            for problem in ('missing','stale','future','crossed','size','nan'):
                s=snapshot()
                if problem=='missing': s['quotes'].pop(index)
                else:
                    q=s['quotes'][index]
                    if problem=='stale': q['updated_at']=(NOW-timedelta(seconds=61)).isoformat()
                    elif problem=='future': q['updated_at']=(NOW+timedelta(seconds=1)).isoformat()
                    elif problem=='crossed': q['bid_price']='99'
                    elif problem=='size': q['ask_size']=0
                    else: q['bid_price']='NaN'
                with self.subTest(index=index,problem=problem):
                    state,e=step(initial_state(),s,NOW,**config())
                    self.assertEqual(e['action'],'NO_TRADE'); self.assertIsNone(state['position'])

    def test_mixed_expiry_chain_am_settlement_zero_dte_and_invalid_wings(self):
        for problem in ('expiry','chain','am','zero_dte','reversed','overlap','center','type'):
            s=snapshot()
            if problem=='expiry': s['instruments'][0]['expiration_date']='2026-10-16'
            elif problem=='chain': s['instruments'][0]['chain_id']='different'
            elif problem=='am': s['chains'][0]['settle_on_open']=True
            elif problem=='zero_dte':
                for i in s['instruments']: i['expiration_date']='2026-10-14'
            elif problem=='reversed': s['instruments'][0]['strike_price']='101'
            elif problem=='overlap': s['instruments'][2]['strike_price']='99'
            elif problem=='center': s['selection']['strategy']='iron_butterfly'
            else: s['instruments'][0]['type']='call'
            strategy='iron_butterfly' if problem=='center' else 'iron_condor'
            with self.subTest(problem=problem):
                self.assertEqual(step(initial_state(),s,NOW,**config(strategy))[1]['action'],'NO_TRADE')

    def test_fee_inclusive_risk_limit_and_negative_or_excessive_fees(self):
        c=config(); c['risk']['max_risk_per_trade']=203
        self.assertEqual(step(initial_state(),snapshot(),NOW,**c)[1]['action'],'NO_TRADE')
        c['risk']['max_risk_per_trade']=204
        self.assertEqual(step(initial_state(),snapshot(),NOW,**c)[1]['action'],'PAPER_ENTRY')
        self.assertEqual(step(initial_state(),snapshot(),NOW,**config(fee='75'))[1]['action'],'NO_TRADE')
        with self.assertRaises(ValueError): step(initial_state(),snapshot(),NOW,**config(fee='-1'))
        state,e=step(initial_state(),snapshot(),NOW,**config(fee='2'))
        self.assertEqual(state['position']['entry_fee'],'8')
        self.assertEqual(state['position']['max_loss'],'216.0')
        self.assertEqual(state['balance'],'3292.0')

    def test_missing_or_stale_exit_leg_keeps_whole_position_cash_and_no_partial_close(self):
        state=self.opened(); later=NOW+timedelta(minutes=10)
        for index in range(4):
            for missing in (True,False):
                s=snapshot(now=later)
                if missing: s['quotes'].pop(index)
                else: s['quotes'][index]['updated_at']=NOW.isoformat()
                after,e=step(state,s,later,**config())
                self.assertEqual(e['action'],'UNRESOLVED')
                self.assertEqual(after['position'],state['position'])
                self.assertEqual(after['balance'],state['balance'])
                self.assertEqual(after['completed'],0)

    def test_stop_uses_credit_multiple_and_closes_all_legs_atomically(self):
        state=self.opened(); later=NOW+timedelta(minutes=10)
        s=snapshot(now=later)
        # Initial close debit 340 > 30% debit-spread loss threshold, but <600 credit stop.
        hold,e=step(state,s,later,**config())
        self.assertEqual(e['action'],'HOLD')
        for q in s['quotes']:
            if q['instrument_id'].startswith('short'): q['ask_price']='3.4'
        after,e=step(state,s,later,**config())
        self.assertEqual(e['action'],'STOP_LOSS')
        self.assertEqual(e['gross_exit_debit'],'600.0')
        self.assertEqual(e['exit_cost'],'602.00')
        self.assertEqual(e['net_pnl'],'-304.00')
        self.assertIsNone(after['position']); self.assertEqual(after['completed'],1)
        self.assertEqual(after['balance'],'2696.00')
        self.assertEqual(len(e['quotes']),4)
        self.assertEqual(accounting(after)['realized_pnl'],'-304.00')

    def test_profit_target_and_session_exit_for_both_strategies(self):
        for strategy in ('iron_condor','iron_butterfly'):
            state=self.opened(strategy); later=NOW+timedelta(minutes=10)
            s=snapshot(strategy,later)
            for q in s['quotes']:
                if q['instrument_id'].startswith('short'): q.update(bid_price='0.8',ask_price='0.9')
            after,e=step(state,s,later,**config(strategy))
            self.assertEqual(e['action'],'TAKE_PROFIT'); self.assertIsNone(after['position'])
            self.assertEqual(e['net_pnl'],'196.00')
            close=NOW.replace(hour=19,minute=30)
            after,e=step(state,snapshot(strategy,close),close,**config(strategy))
            self.assertEqual(e['action'],'TIME_EXIT'); self.assertIsNone(after['position'])

    def test_asymmetric_wings_use_wider_side_and_configured_daily_limits(self):
        s=snapshot(); s['instruments'][3]['strike_price']='120'
        c=config(); c['risk']['max_risk_per_trade']=1000; c['risk']['max_total_open_risk']=1000
        state,e=step(initial_state(),s,NOW,**c)
        self.assertEqual(e['action'],'PAPER_ENTRY'); self.assertEqual(state['position']['max_loss'],'704.00')
        s=snapshot(); state=initial_state(); state['daily_pnl'][NOW.date().isoformat()]='-750'
        self.assertEqual(step(state,s,NOW,**config())[1]['action'],'NO_TRADE')

    def test_archive_replay_and_accounting_detect_credit_corruption(self):
        for strategy in ('iron_condor','iron_butterfly'):
            archive=observe(new_archive(strategy),snapshot(strategy),NOW)
            later=NOW.replace(hour=19,minute=30)
            archive=observe(archive,snapshot(strategy,later),later)
            state,report=replay(archive)
            self.assertEqual(report['completed_trades'],1)
            self.assertEqual(report['cash'],'2956.00')
            self.assertEqual(replay(archive),(state,report))
            state['events'][0]['position']['max_loss']='1'
            with self.assertRaises(ValueError): accounting(state)

    def test_early_close_time_exit_and_frozen_config(self):
        from datetime import datetime, timezone
        entry=datetime(2026,11,27,15,0,tzinfo=timezone.utc)
        later=datetime(2026,11,27,17,30,tzinfo=timezone.utc)
        s=snapshot(now=entry)
        for i in s['instruments']: i['expiration_date']='2026-11-30'
        archive=observe(new_archive('iron_condor'),s,entry)
        s=snapshot(now=later)
        for i in s['instruments']: i['expiration_date']='2026-11-30'
        archive=observe(archive,s,later)
        state,report=replay(archive)
        self.assertEqual(state['events'][-1]['action'],'TIME_EXIT')
        from unittest.mock import patch
        with patch('credit_paper.SETTINGS',object()):
            self.assertEqual(replay(archive),(state,report))

    def test_pipeline_persisted_credit_archive_fixture_separation_and_0dte_guard(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fixture.json'; archive=Path(tmp)/'fixture-archive.json'
            env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
            command=[sys.executable,str(root/'paper_pipeline.py'),str(source),'--archive',str(archive),
                     '--historical','--allow-fixtures','--strategy','iron_condor']
            for index,now in enumerate((NOW,NOW.replace(hour=19,minute=30))):
                b=bundle(now); b['options']=snapshot(now=now)
                source.write_text(json.dumps(b))
                run=subprocess.run(command+(['--init'] if index==0 else []),env=env,text=True,capture_output=True)
                self.assertEqual(run.returncode,0,run.stderr)
                self.assertEqual(json.loads(run.stdout)['action'],'PAPER_ENTRY' if index==0 else 'TIME_EXIT')
            run=subprocess.run([sys.executable,str(root/'paper_replay.py'),str(archive)],env=env,text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
            self.assertEqual(json.loads(run.stdout)['completed_trades'],1)
            before=archive.read_bytes()
            for changed_env in (dict(env,ALLOW_0DTE='true'),dict(env,ROBINHOOD_LIVE_ORDERS='true')):
                self.assertNotEqual(subprocess.run(command,env=changed_env,capture_output=True).returncode,0)
            b['source']={'kind':'observed','name':'not a real export'}
            b['observed_at']=(NOW.replace(hour=19,minute=30)+timedelta(seconds=1)).isoformat()
            source.write_text(json.dumps(b))
            self.assertNotEqual(subprocess.run(command,env=env,capture_output=True).returncode,0)
            self.assertEqual(archive.read_bytes(),before)
