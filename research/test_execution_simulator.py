import tempfile
import unittest
from pathlib import Path
from execution_simulator import ExecutionSimulator

class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'sim.sqlite'
        self.sim=ExecutionSimulator(self.path)
    def tearDown(self): self.tmp.cleanup()
    def entry(self):
        return self.sim.apply('entry','submit_entry',order_id='o1',quantity=1,max_loss_after_costs=25)
    def report(self,event,oid,status,filled):
        return self.sim.apply(event,'report',order_id=oid,status=status,cumulative_filled=filled,evidence='synthetic fixture')
    def test_fill_exit_halt(self):
        self.entry();self.report('fill','o1','filled',1)
        self.sim.apply('stop','halt')
        self.sim.apply('exit','submit_exit',order_id='x1',quantity=1)
        s=self.report('closed','x1','filled',1)
        self.assertEqual(s['quantity'],0)
        with self.assertRaises(ValueError):
            self.sim.apply('new','submit_entry',order_id='o2',quantity=1,max_loss_after_costs=20)
    def test_timeout_restart_no_duplicate(self):
        self.entry();self.sim.apply('timeout','timeout',order_id='o1')
        self.sim=ExecutionSimulator(self.path)
        self.assertEqual(self.sim.state()['phase'],'unknown')
        with self.assertRaises(ValueError):
            self.sim.apply('retry','submit_entry',order_id='o2',quantity=1,max_loss_after_costs=25)
        self.report('fill','o1','filled',1)
        self.report('fill','o1','filled',1)
        self.assertEqual(self.sim.state()['quantity'],1)
        with self.assertRaises(ValueError): self.report('fill','o1','filled',0)
    def test_rejection_and_exit_rejection(self):
        self.entry();self.report('reject','o1','rejected',0)
        self.sim.apply('new','submit_entry',order_id='o2',quantity=1,max_loss_after_costs=25)
        self.report('fill','o2','filled',1)
        self.sim.apply('exit','submit_exit',order_id='x1',quantity=1)
        s=self.report('fail_exit','x1','rejected',0)
        self.assertEqual(s['phase'],'open');self.assertEqual(s['quantity'],1)
    def test_partial_legs_halt(self):
        self.entry()
        with self.assertRaises(ValueError): self.report('fraction','o1','partial',0.5)
        s=self.sim.apply('legs','leg_mismatch')
        self.assertTrue(s['halted']);self.assertEqual(s['phase'],'reconciliation_required')
        with self.assertRaises(ValueError):
            self.sim.apply('retry','submit_entry',order_id='o2',quantity=1,max_loss_after_costs=25)
    def test_risk_and_atomic_rollback(self):
        for risk in (31,-1,'NaN'):
            with self.assertRaises(ValueError):
                self.sim.apply('bad','submit_entry',order_id='bad',quantity=1,max_loss_after_costs=risk)
        self.assertEqual(self.sim.state()['sequence'],0)
        self.entry()
        with self.assertRaises(ValueError):self.report('badfill','o1','filled',2)
        self.assertEqual(self.sim.state()['quantity'],0)

if __name__=='__main__':unittest.main()
