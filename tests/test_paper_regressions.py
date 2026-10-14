"""Regression fixtures for exit resilience, early closes, and lock collisions."""
from datetime import datetime, timedelta, timezone
from decimal import InvalidOperation
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from credit_paper import configured_risk
from ndx_paper import initial_state, step
from paper_pipeline import build_snapshot
from test_credit_paper import snapshot, config
from test_paper_pipeline import bundle, NOW


class PaperRegressionTests(unittest.TestCase):
    def test_bad_decimal_candle_does_not_block_whole_position_exit(self):
        state,_=step(initial_state(),snapshot(),NOW,**config())
        later=NOW.replace(hour=19,minute=30)
        b=bundle(later); b['options']=snapshot(now=later)
        b['candles'][0]['close']='bad-price'
        with self.assertRaises((ValueError,InvalidOperation)):
            build_snapshot(b,later,allow_fixtures=True)
        outgoing=build_snapshot(b,later,allow_fixtures=True,exit_only=True)
        self.assertIsNotNone(outgoing['provenance']['history_unavailable'])
        after,event=step(state,outgoing,later,**config())
        self.assertEqual(event['action'],'TIME_EXIT')
        self.assertIsNone(after['position'])
        self.assertEqual(after['completed'],1)

    def test_entry_closes_at_early_close_exit_threshold(self):
        for minute,action in ((29,'PAPER_ENTRY'),(30,'NO_TRADE'),(45,'NO_TRADE')):
            now=datetime(2026,11,27,17,minute,tzinfo=timezone.utc)
            s=snapshot(now=now)
            for i in s['instruments']: i['expiration_date']='2026-11-30'
            state,event=step(initial_state(),s,now,**config())
            self.assertEqual(event['action'],action)
            if action=='NO_TRADE': self.assertIsNone(state['position'])

    def test_matching_archive_and_portfolio_stems_do_not_deadlock(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fixture.json'; archive=Path(tmp)/'fixture-portfolio.json'
            b=bundle(); b['options']=snapshot(); source.write_text(json.dumps(b))
            env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
            cmd=[sys.executable,str(root/'paper_pipeline.py'),str(source),'--archive',str(archive),
                 '--strategy','iron_condor','--historical','--allow-fixtures','--init']
            p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            try:
                stdout,stderr=p.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill(); p.communicate()
                self.fail('Archive/portfolio lock collision deadlocked the pipeline')
            self.assertEqual(p.returncode,0,stderr)
            self.assertEqual(json.loads(stdout)['action'],'PAPER_ENTRY')
            replay=subprocess.run([sys.executable,str(root/'paper_replay.py'),str(archive)],env=env,
                                  capture_output=True,text=True,timeout=5)
            self.assertEqual(replay.returncode,0,replay.stderr)

    def test_explicit_overlapping_lock_override_is_rejected_before_acquisition(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'fixture.json'; archive=Path(tmp)/'condor.json'
            portfolio=Path(tmp)/'condor.json.archive.sqlite3'
            b=bundle(); b['options']=snapshot(); source.write_text(json.dumps(b))
            env=dict(os.environ,TRADING_MODE='paper',ROBINHOOD_LIVE_ORDERS='false',ALLOW_0DTE='false')
            cmd=[sys.executable,str(root/'paper_pipeline.py'),str(source),'--archive',str(archive),
                 '--portfolio',str(portfolio),'--strategy','iron_condor','--historical','--allow-fixtures','--init']
            result=subprocess.run(cmd,env=env,capture_output=True,text=True,timeout=5)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Archive lock must not overlap',result.stderr)
            self.assertFalse(archive.exists()); self.assertFalse(portfolio.exists())
