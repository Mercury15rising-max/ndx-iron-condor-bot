"""QQQ-only offline research. Never authenticates, places orders, or changes ledgers."""
import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from statistics import mean

from ema_signals import ema, stamp

VERSION = 'qqq-research-v1'
QQQ_MAX_TOTAL_LOSS = 450.0
QQQ_MIN_QUANTITY = 10


def trend_report(payload, as_of):
    """Analyze only completed daily QQQ bars known at the requested cutoff."""
    if as_of.tzinfo is None:
        raise ValueError('Timezone-aware as_of required')
    if payload.get('symbol') != 'QQQ' or payload.get('interval') != 'day':
        raise ValueError('QQQ daily history required')
    bars, excluded, previous = [], 0, None
    for bar in payload['bars']:
        start = stamp(bar['begins_at'])
        if previous is not None and start <= previous:
            raise ValueError('Duplicate or unordered dates')
        previous = start
        # Conservative daily completion boundary; never includes the current UTC day.
        if bar.get('interpolated') or start + timedelta(days=1) > as_of:
            excluded += 1
            continue
        o, h, l, c = (float(bar[k]) for k in ('open_price', 'high_price', 'low_price', 'close_price'))
        volume = float(bar['volume'])
        if not all(isfinite(v) and v > 0 for v in (o, h, l, c)) or not l <= min(o, c) <= max(o, c) <= h:
            raise ValueError('Invalid OHLC')
        if not isfinite(volume) or volume < 0:
            raise ValueError('Invalid volume')
        bars.append((start, h, l, c))
    if len(bars) < 106:
        raise ValueError('At least 106 completed daily bars required')
    closes = [b[3] for b in bars]
    curves = {p: ema(closes, p)[-1] for p in (8, 13, 21)}
    sma20, sma50 = mean(closes[-20:]), mean(closes[-50:])
    y = closes[-20:]
    slope = sum((i - 9.5) * (v - mean(y)) for i, v in enumerate(y)) / 665
    tr = [max(b[1] - b[2], abs(b[1] - bars[i][3]), abs(b[2] - bars[i][3])) for i, b in enumerate(bars[1:])]
    atr = mean(tr[-14:])
    bullish = curves[8] > curves[13] > curves[21] and closes[-1] > sma20 > sma50 and slope > 0
    bearish = curves[8] < curves[13] < curves[21] and closes[-1] < sma20 < sma50 and slope < 0
    # Explicit heuristic, not a fitted probability or a validated trading edge.
    sideways = abs(slope) <= 0.05 * atr and abs(curves[8] - curves[21]) <= 0.25 * atr
    regime = 'bullish' if bullish else 'bearish' if bearish else 'sideways' if sideways else 'mixed'
    families = {'bullish': ['bull_call_debit_spread', 'bull_put_credit_spread'],
                'bearish': ['bear_put_debit_spread', 'bear_call_credit_spread'],
                'sideways': ['iron_condor'], 'mixed': []}
    returns = [b / a - 1 for a, b in zip(closes, closes[1:])]
    stale = (as_of - bars[-1][0]).total_seconds() > 7 * 86400
    return {'version': VERSION, 'symbol': 'QQQ', 'research_only': True,
            'as_of': as_of.isoformat(), 'last_session': bars[-1][0].date().isoformat(),
            'sessions': len(bars), 'excluded_bars': excluded, 'stale': stale,
            'last_close': closes[-1], 'ema': curves, 'sma20': sma20, 'sma50': sma50,
            'sma100': mean(closes[-100:]), 'slope20_points_per_session': slope,
            'atr14': atr, 'return_total': closes[-1] / closes[0] - 1,
            'return5': closes[-1] / closes[-6] - 1,
            'daily_return_std20': mean([(v - mean(returns[-20:])) ** 2 for v in returns[-20:]]) ** 0.5,
            'regime': regime, 'strategy_families_to_research': [] if stale else families[regime],
            'entry_approved': False,
            'limitations': ['Daily trend is context, not an intraday entry signal.',
                           'Requires fresh options quotes, event checks and fee-inclusive total risk.',
                           'No option P&L can be inferred from underlying history alone.',
                           'Missing trading sessions are not reconstructed; source completeness is not certified.']}


def total_risk(per_unit_loss, quantity, total_fees, risk_cap):
    """All fees must include the planned entry and exit; no default position size."""
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError('Positive integer quantity required')
    if not all(isfinite(v) and v >= 0 for v in (per_unit_loss, total_fees, risk_cap)):
        raise ValueError('Finite nonnegative risk and fees required')
    loss = round(per_unit_loss * quantity + total_fees, 8)
    effective_cap = min(risk_cap, QQQ_MAX_TOTAL_LOSS)
    return {'quantity': quantity, 'minimum_quantity': QQQ_MIN_QUANTITY,
            'max_loss_including_fees': loss, 'risk_cap': effective_cap,
            'within_cap': loss <= effective_cap,
            'quantity_eligible': quantity >= QQQ_MIN_QUANTITY,
            'eligible': quantity >= QQQ_MIN_QUANTITY and loss <= effective_cap}


def archive_payload(payload, root, source, captured_at):
    """Content-addressed immutable JSON; preserves original observations and timestamps."""
    if not source.strip() or captured_at.tzinfo is None:
        raise ValueError('Source and aware capture time required')
    record = {'schema_version': 1, 'source': source, 'captured_at': captured_at.isoformat(),
              'research_only': True, 'payload': payload}
    raw = (json.dumps(record, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    digest = hashlib.sha256(raw).hexdigest()
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    target = root / (digest + '.json')
    try:
        with target.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        if target.read_bytes() != raw:
            raise ValueError('Archive integrity mismatch')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='QQQ result object: symbol, interval, bars')
    parser.add_argument('--source', required=True)
    parser.add_argument('--as-of', required=True, help='Aware historical analysis cutoff')
    parser.add_argument('--archive-dir', type=Path, default=Path('research/qqq/snapshots'))
    args = parser.parse_args()
    payload = json.loads(args.input.read_text())
    report = trend_report(payload, stamp(args.as_of))
    now = datetime.now(timezone.utc)
    raw_path = archive_payload(payload, args.archive_dir, args.source, now)
    report['input_archive_sha256'] = raw_path.stem
    report_path = archive_payload(report, args.archive_dir, VERSION, now)
    print(json.dumps({'input_archive': str(raw_path), 'report_archive': str(report_path), 'report': report}, indent=2))


if __name__ == '__main__':
    main()
