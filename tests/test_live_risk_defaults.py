import unittest
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

from config import Settings
from risk_manager import evaluate_trade
from safety_gate import evaluate_entry_safety


class LiveRiskDefaultsTests(unittest.TestCase):
    def decision(self, risk, pnl=0):
        return evaluate_trade(
            SimpleNamespace(max_loss=risk), max_risk_per_trade=75,
            daily_realized_pnl=pnl, max_daily_loss=75,
            open_positions=0, max_open_positions=1,
            trades_today=0, max_trades_per_day=1,
        )

    def test_default_risk_limits(self):
        env = dict(os.environ)
        for name in ('MAX_RISK_PER_TRADE', 'MAX_DAILY_LOSS', 'MAX_TOTAL_OPEN_RISK'):
            env.pop(name, None)
        result = subprocess.run([
            sys.executable, '-c',
            'import json; from config import Settings; s=Settings(); '
            'print(json.dumps([s.max_risk_per_trade,s.max_daily_loss,s.max_total_open_risk]))',
        ], env=env, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [75, 75, 75])

    def test_per_trade_boundary(self):
        self.assertTrue(self.decision(75).approved)
        self.assertFalse(self.decision(75.01).approved)

    def test_daily_stop(self):
        self.assertFalse(self.decision(1, -75).approved)
        now = datetime.now(timezone.utc)
        self.assertEqual(evaluate_entry_safety(
            quote_timestamp=now, now=now, daily_realized_pnl=-75,
        ).action, 'kill_switch')
