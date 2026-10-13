import unittest
from datetime import datetime, timedelta, timezone
from regime_comparison import context, variants

class RegimeTests(unittest.TestCase):
    def test_history_and_lookahead(self):
        start = datetime(2025, 1, 1)
        days = [start + timedelta(days=i) for i in range(400)]
        days = [d for d in days if d.weekday() < 5][:230]
        bars = [dict(begins_at=d.isoformat(), close_price=str(100+i*.1))
                for i,d in enumerate(days)]
        session = days[-1].date().isoformat()
        now = (days[-1] + timedelta(days=1, hours=16)).replace(tzinfo=timezone.utc)
        entry = dict(symbol='TEST', interval='day', bounds='regular', bars=bars)
        original = context(entry, session, now)
        bars.append(dict(begins_at=now.isoformat(), close_price='999999'))
        updated = context(entry, session, now)
        self.assertEqual(updated.pop('excluded_bars'), 1)
        original.pop('excluded_bars')
        self.assertEqual(original, updated)
        self.assertEqual(original['status'], 'ok')
        self.assertIsNotNone(original['rv60_daily_pct'])
        with self.assertRaises(ValueError):
            context(entry, now.date().isoformat(), now)

    def test_filters_never_override_risk(self):
        feature = dict(status='ok', regime='mixed', volatility_filter=True)
        self.assertEqual(set(variants({'status':'rejected'}, feature).values()),
                         {'blocked_by_existing_gates'})
        self.assertEqual(variants({'status':'research_candidate'}, None)['combined'],
                         'missing_or_stale_history')
        feature['volatility_filter'] = False
        self.assertEqual(variants({'status':'research_candidate'}, feature)['combined'],
                         'filter_skip')

if __name__ == '__main__':
    unittest.main()
