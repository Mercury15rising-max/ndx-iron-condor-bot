"""Validate candle continuity against an explicit exchange schedule snapshot."""
from datetime import datetime, timedelta


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone-aware schedule timestamps required')
    return result


def expected_closes(calendar, first, last, seconds):
    if calendar.get('complete') is not True or not calendar.get('source'):
        raise ValueError('Complete sourced session calendar required')
    start, end = stamp(calendar['coverage_start']), stamp(calendar['coverage_end'])
    if not start <= first <= last <= end:
        raise ValueError('Session calendar does not cover candle history')
    expected = []
    previous_end = None
    for session in calendar['sessions']:
        opening, closing = stamp(session['open']), stamp(session['close'])
        if not start <= opening < closing <= end:
            raise ValueError('Invalid session bounds')
        if previous_end is not None and opening <= previous_end:
            raise ValueError('Overlapping or unordered sessions')
        if (closing - opening).total_seconds() % seconds:
            raise ValueError('Session length is not aligned to timeframe')
        previous_end = closing
        cursor = opening + timedelta(seconds=seconds)
        while cursor <= closing:
            if first <= cursor <= last:
                expected.append(cursor)
            cursor += timedelta(seconds=seconds)
    return expected


def normalize_robinhood(series, now):
    """Convert left-edge labels to close times; never sort/fill bad history."""
    if series['interval'] != '5minute' or series['bounds'] != 'regular':
        raise ValueError('Expected regular-session five-minute history')
    result = []
    for bar in series['bars']:
        end = stamp(bar['begins_at']) + timedelta(minutes=5)
        result.append(dict(symbol=series['symbol'], timeframe_seconds=300,
                           close_time=end.isoformat(), closed=end <= now,
                           close=bar['close_price'], high=bar['high_price'],
                           low=bar['low_price'], volume=bar['volume'],
                           volume_type='trade', interpolated=bar.get('interpolated', False)))
    return result
