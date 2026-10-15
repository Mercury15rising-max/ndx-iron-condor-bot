import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from qqq_research import archive_payload, total_risk, trend_report


class QQQResearchTests(unittest.TestCase):
    def history(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return {'symbol': 'QQQ', 'interval': 'day', 'bars': [
            {'begins_at': (start + timedelta(days=i)).isoformat(),
             'open_price': 100 + i, 'high_price': 102 + i,
             'low_price': 99 + i, 'close_price': 101 + i, 'volume': 100}
            for i in range(120)]}

    def test_future_data_does_not_change_past_decision(self):
        data = self.history()
        cutoff = datetime(2026, 4, 25, tzinfo=timezone.utc)
        expected = trend_report(data, cutoff)
        data['bars'][-1]['close_price'] = 999999
        actual = trend_report(data, cutoff)
        self.assertEqual(expected, actual)
        self.assertEqual(actual['regime'], 'bullish')
        self.assertFalse(actual['entry_approved'])

    def test_duplicate_and_bad_prices_rejected(self):
        data = self.history()
        data['bars'][-1]['begins_at'] = data['bars'][-2]['begins_at']
        with self.assertRaises(ValueError):
            trend_report(data, datetime(2026, 5, 1, tzinfo=timezone.utc))
        data = self.history()
        data['bars'][0]['high_price'] = float('nan')
        with self.assertRaises(ValueError):
            trend_report(data, datetime(2026, 5, 1, tzinfo=timezone.utc))

    def test_stale_history_cannot_nominate_strategy(self):
        r = trend_report(self.history(), datetime(2026, 6, 1, tzinfo=timezone.utc))
        self.assertTrue(r['stale'])
        self.assertEqual(r['strategy_families_to_research'], [])

    def test_quantity_and_fees_are_total_not_per_contract(self):
        self.assertEqual(total_risk(37, 12, 6, 50)['max_loss_including_fees'], 450)
        self.assertFalse(total_risk(37, 12, 6, 50)['within_cap'])
        self.assertTrue(total_risk(37, 1, 6, 50)['within_cap'])
        with self.assertRaises(ValueError):
            total_risk(37, True, 0, 50)

    def test_immutable_archive_is_idempotent_and_detects_corruption(self):
        with tempfile.TemporaryDirectory() as root:
            at = datetime(2026, 5, 1, tzinfo=timezone.utc)
            path = archive_payload(self.history(), root, 'test', at)
            self.assertEqual(path, archive_payload(self.history(), root, 'test', at))
            self.assertEqual(json.loads(path.read_text())['payload'], self.history())
            path.write_text('corrupt')
            with self.assertRaises(ValueError):
                archive_payload(self.history(), root, 'test', at)


if __name__ == '__main__':
    unittest.main()
