"""Dated descriptive context; never authorizes a trade or substitutes a proxy."""
import math
from datetime import date, timedelta


def lookup(payload, symbol, completed_session):
    rows = payload['results']
    matches = [r for r in rows if r['symbol'] == symbol]
    if len(matches) != 1:
        return {'status': 'missing_or_duplicate_symbol', 'symbol': symbol}
    row = matches[0]
    if row['end'] != completed_session:
        return {'status': 'stale_context', 'symbol': symbol, 'data_session': row['end']}
    numeric = ('return_pct', 'close_sample_drawdown_pct', 'rv20_daily_pct',
               'rv60_daily_pct', 'above_sma200_pct', 'correlation_to_SPY')
    if row['sessions'] != 200 or any(not math.isfinite(float(row[k])) for k in numeric):
        raise ValueError('Invalid 200-session research context')
    peers = []
    for pair in payload['correlations']:
        if symbol not in (pair['a'], pair['b']):
            continue
        corr = float(pair['correlation'])
        if not math.isfinite(corr) or not -1 <= corr <= 1:
            raise ValueError('Invalid correlation')
        peers.append({'symbol': pair['b'] if pair['a'] == symbol else pair['a'],
                      'correlation': corr})
    return dict(status='ok', symbol=symbol, observations=row,
                closest_co_movers=sorted(peers, key=lambda p: -abs(p['correlation']))[:3],
                role='context_only', authorizes_trade=False,
                interpretation='Historical price behavior; not option profitability or a forecast')
