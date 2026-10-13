"""Shadow comparisons only: no orders, fills, or claims of profitability."""
import argparse
import json
import math
import statistics
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from trend_features import analyze
from paper_strategy_lab import compare
from paper_ledger import PaperLedger


def context(entry, session, as_of):
    if as_of.tzinfo is None:
        raise ValueError('Timezone required')
    if date.fromisoformat(session) >= as_of.astimezone(ZoneInfo('America/New_York')).date():
        raise ValueError('Use a completed session strictly before evaluation day')
    result = analyze(entry, session)
    bars = sorted((b for b in entry['bars'] if b and not b.get('interpolated')
                   and b['begins_at'][:10] <= session), key=lambda b: b['begins_at'])
    prices = [float(b['close_price']) for b in bars]
    returns = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    result.update(rv20_daily_pct=None, rv60_daily_pct=None, volatility_filter=None)
    if len(returns) >= 60:
        short = statistics.stdev(returns[-20:]) * 100
        long = statistics.stdev(returns[-60:]) * 100
        result.update(rv20_daily_pct=short, rv60_daily_pct=long,
                      volatility_filter=short <= long)
    return result


def variants(candidate, feature):
    """Preserve all existing gates; experimental filters only narrow eligibility."""
    base = candidate['status'] == 'research_candidate'
    valid = bool(feature and feature.get('status') == 'ok'
                 and feature.get('volatility_filter') is not None)
    trend = valid and feature['regime'] == 'mixed'
    vol = valid and feature['volatility_filter']
    checks = {'baseline': True, 'mixed_trend': trend,
              'volatility_not_expanding': vol, 'combined': trend and vol}
    return {name: ('blocked_by_existing_gates' if not base else
                   'missing_or_stale_history' if name != 'baseline' and not valid else
                   'shadow_eligible' if passed else 'filter_skip')
            for name, passed in checks.items()}


def run(snapshot, histories, session, ledger):
    if histories.get('adjustment_type') != 'split':
        raise ValueError('Explicit split-adjusted histories required')
    now = datetime.fromisoformat(snapshot['as_of'].replace('Z', '+00:00'))
    entries = {}
    for entry in histories['results']:
        if entry['symbol'] in entries:
            raise ValueError('Duplicate history symbol')
        entries[entry['symbol']] = entry
    features = {}
    for symbol in {q['symbol'] for q in snapshot['quotes']}:
        try:
            features[symbol] = context(entries[symbol], session, now)
        except (KeyError, ValueError, TypeError) as exc:
            features[symbol] = {'status': 'data_error', 'reason': str(exc)}
    output = []
    for candidate in compare(snapshot['quotes'], now):
        row = ledger.gate(candidate, snapshot['as_of'])
        feature = features.get(row['symbol'])
        row.update(market_context=feature, shadow_variants=variants(row, feature),
                   experiment_version='regime_v1', filled=False)
        output.append(row)
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot')
    p.add_argument('histories')
    p.add_argument('--completed-session', required=True)
    p.add_argument('--ledger', required=True)
    p.add_argument('--journal', required=True)
    a = p.parse_args()
    rows = run(json.loads(Path(a.snapshot).read_text()),
               json.loads(Path(a.histories).read_text()), a.completed_session,
               PaperLedger(a.ledger))
    with open(a.journal, 'a') as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
    print(json.dumps({'evaluations': len(rows), 'fills': 0,
                      'experiment': 'shadow_only'}))
