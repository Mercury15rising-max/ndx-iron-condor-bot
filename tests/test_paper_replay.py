import unittest
from copy import deepcopy
from datetime import timedelta
from test_ndx_paper import NOW, data
from paper_replay import new_archive, observe, replay, accounting


class ReplayTests(unittest.TestCase):
    def test_exact_replay_and_independent_cash(self):
        archive = observe(new_archive(), data(), NOW)
        later = NOW + timedelta(minutes=10)
        archive = observe(archive, data(later), later)
        state, report = replay(archive)
        self.assertEqual(replay(archive), (state, report))
        self.assertEqual(report['completed_trades'], 1)
        self.assertEqual(report['cash'], state['balance'])
        self.assertEqual(report['goal'], 'INCOMPLETE')

    def test_alteration_and_sequence_rejected(self):
        archive = observe(new_archive(), data(), NOW)
        for field, value in [('sequence', 2), ('observed_at', '2026-10-14T18:00:00+00:00'), ('previous', 'bad')]:
            modified = deepcopy(archive)
            modified['records'][0][field] = value
            with self.assertRaises(ValueError): replay(modified)

    def test_source_and_config_mismatch(self):
        for field in ('implementation', 'config'):
            archive = new_archive(); archive[field] = 'wrong'
            with self.assertRaises(ValueError): replay(archive)

    def test_duplicate_time_and_input_immutability(self):
        original = new_archive(); snapshot = data()
        archive = observe(original, snapshot, NOW)
        self.assertEqual(original['records'], [])
        snapshot['signal_symbol'] = 'CHANGED'
        self.assertEqual(archive['records'][0]['snapshot']['signal_symbol'], 'QQQ')
        with self.assertRaises(ValueError): observe(archive, data(), NOW)

    def test_independent_accounting_detects_corruption(self):
        state, _ = replay(observe(new_archive(), data(), NOW))
        state['balance'] = '3000'
        with self.assertRaises(ValueError): accounting(state)
