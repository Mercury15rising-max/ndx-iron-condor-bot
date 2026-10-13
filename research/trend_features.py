"""Daily watchlist research; no order submission or strategy authorization."""
import argparse
import json
import math
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def analyze(entry, completed_session):
    """Provider daily UTC labels represent session dates, not local midnights."""
    if entry['interval'] != 'day' or entry['bounds'] != 'regular':
        raise ValueError('Requires regular daily bars')
    cutoff = date.fromisoformat(completed_session)
    closes = {}
    excluded = 0
    for bar in entry.get('bars') or []:
        if bar is None or bar.get('interpolated'):
            excluded += 1
            continue
        day = date.fromisoformat(bar['begins_at'][:10])
        if day > cutoff:
            excluded += 1
            continue
        value = float(bar['close_price'])
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid close')
        if day in closes:
            raise ValueError('Duplicate session')
        closes[day] = value
    days = sorted(closes)
    values = [closes[d] for d in days]
    result = dict(symbol=entry['symbol'], completed_session=completed_session,
                  last_session=days[-1].isoformat() if days else None,
                  observations=len(values), excluded_bars=excluded,
                  role='context_only', price_basis='split_adjusted_bar_close',
                  status='ok', sma50=None, sma200=None, slope200_20_pct=None,
                  distance200_pct=None, distance50_pct=None, regime='unknown',
                  close=values[-1] if values else None)
    if len(values) >= 50:
        result['sma50'] = sum(values[-50:]) / 50
        result['distance50_pct'] = (values[-1] / result['sma50'] - 1) * 100
    if len(values) >= 200:
        result['sma200'] = sum(values[-200:]) / 200
        result['distance200_pct'] = (values[-1] / result['sma200'] - 1) * 100
    if len(values) >= 220:
        prior = sum(values[-220:-20]) / 200
        result['slope200_20_pct'] = (result['sma200'] / prior - 1) * 100
    if not days or days[-1] != cutoff:
        result['status'] = 'stale_or_missing_session'
    elif len(values) < 220:
        result['status'] = 'insufficient_history'
    else:
        above = values[-1] > result['sma200']
        slope = result['slope200_20_pct']
        result['regime'] = ('bullish' if above and slope > 0 else
                            'bearish' if not above and slope < 0 else 'mixed')
    return result


def collect(payload, symbols, completed_session, database):
    if payload.get('adjustment_type') != 'split':
        raise ValueError('Explicit split adjustment required')
    entries = {e['symbol']: e for e in payload['results']}
    records = []
    captured = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS trend_snapshots '
                   '(symbol TEXT, session TEXT, payload TEXT, PRIMARY KEY(symbol,session))')
        for symbol in symbols:
            try:
                result = analyze(entries[symbol], completed_session)
            except (KeyError, ValueError, TypeError) as exc:
                result = dict(symbol=symbol, status='data_error', reason=str(exc),
                              regime='unknown', role='context_only')
            result.update(source=payload.get('source', 'unspecified'),
                          captured_at_utc=captured, completed_session=completed_session)
            db.execute('INSERT OR REPLACE INTO trend_snapshots VALUES (?,?,?)',
                       (symbol, completed_session, json.dumps(result, allow_nan=False)))
            records.append(result)
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', help='JSON: adjustment_type=split, source, results[]')
    parser.add_argument('--completed-session', required=True,
                        help='Last completed exchange session YYYY-MM-DD; caller must resolve holidays')
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    from research_watchlist import DEFAULT_RESEARCH_WATCHLIST
    records = collect(json.loads(Path(args.input).read_text()),
                      [a.symbol for a in DEFAULT_RESEARCH_WATCHLIST],
                      args.completed_session, args.database)
    print(json.dumps(records, indent=2))
