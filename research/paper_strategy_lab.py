"""Offline quote-snapshot research. No broker, orders, or assumed fills."""
import argparse
import itertools
import json
import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

try:
    from .research_risk_policy import STARTING_BALANCE, risk_limits
except ImportError:
    from research_risk_policy import STARTING_BALANCE, risk_limits



def evaluate(legs, now, fee=1.0, slippage=0.1):
    """Leg order: long put, short put, short call, long call; one lot each.

    Prices in index points, costs in dollars. Assumed multiplier: 100.
    Limits deliberately fixed for this research experiment, not Railway settings.
    """
    reasons = []
    if now.tzinfo is None:
        raise ValueError('now must include a timezone')
    if any(not math.isfinite(float(v)) or v < 0 for v in (fee, slippage)):
        raise ValueError('cost assumptions cannot be negative')
    if len(legs) != 4:
        raise ValueError('four legs required')
    lp, sp, sc, lc = legs
    if len({(q['symbol'], q['expiration']) for q in legs}) != 1:
        raise ValueError('mixed symbol or expiration')
    if [q['option_type'] for q in legs] != ['put', 'put', 'call', 'call']:
        raise ValueError('invalid leg types')
    if not lp['strike'] < sp['strike'] <= sc['strike'] < lc['strike']:
        raise ValueError('invalid strike order')
    for q in legs:
        if any(not math.isfinite(float(q[k])) for k in ('bid', 'ask', 'strike', 'delta')):
            raise ValueError('nonfinite quote')
        if q['bid'] < 0 or q['ask'] < q['bid']:
            raise ValueError('invalid quote market')
        if q.get('multiplier', 100) != 100:
            raise ValueError('only standard 100-multiplier contracts supported')
        try:
            stamp = datetime.fromisoformat(q['quote_timestamp'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError()
            age = (now - stamp).total_seconds()
            if age < -2 or age > 30:
                reasons.append('stale_or_future_quote')
        except (ValueError, KeyError, TypeError):
            reasons.append('missing_or_invalid_timestamp')
        mid = (q['ask'] + q['bid']) / 2
        if q['bid'] < .1 or q['ask'] - q['bid'] > 2.5 or mid <= 0 or (q['ask'] - q['bid']) / mid > .2:
            reasons.append('spread_or_bid_limit')
        if q.get('open_interest') is None or not math.isfinite(float(q['open_interest'])) or q['open_interest'] < 50:
            reasons.append('open_interest_below_50')
        if q.get('volume') is None or not math.isfinite(float(q['volume'])) or q['volume'] < 10:
            reasons.append('volume_below_10')
    local = now.astimezone(ZoneInfo('America/New_York'))
    dte = (date.fromisoformat(sp['expiration']) - local.date()).days
    if dte <= 0:
        reasons.append('zero_dte_or_expired')
    if local.weekday() >= 5 or not '10:00' <= local.strftime('%H:%M') < '14:30':
        reasons.append('outside_entry_window')
    width = max(sp['strike'] - lp['strike'], lc['strike'] - sc['strike'])
    mid_credit = sum((q['bid'] + q['ask']) / 2 * sign for q, sign in zip(legs, [-1, 1, 1, -1]))
    credit = sp['bid'] + sc['bid'] - lp['ask'] - lc['ask'] - 4 * slippage
    # Reserve fees for entry AND exit, including expiration comparisons.
    costs = 8 * fee
    profit = credit * 100 - costs
    loss = (width - credit) * 100 + costs
    if mid_credit <= 0 or mid_credit >= width or credit >= width:
        reasons.append('inconsistent_package_pricing')
    if credit <= 0 or profit <= 0:
        reasons.append('nonpositive_credit_after_costs')
    cap, daily_cap = risk_limits(STARTING_BALANCE)
    if loss > float(cap) or loss <= 0:
        reasons.append('per_trade_risk')
    if credit / width < .1 or (loss > 0 and profit / loss < .1):
        reasons.append('insufficient_return_on_risk')
    return dict(strategy='iron_butterfly' if sp['strike'] == sc['strike'] else 'iron_condor',
                symbol=sp['symbol'], expiration=sp['expiration'], dte=dte,
                strikes=[q['strike'] for q in legs], evaluated_at=now.isoformat(),
                midpoint_credit_points=round(mid_credit, 4), conservative_credit_points=round(credit, 4),
                max_profit_after_costs=round(profit, 2), max_loss_after_costs=round(loss, 2),
                reasons=sorted(set(reasons)), status='rejected' if reasons else 'research_candidate',
                filled=False, fee_per_contract=fee, slippage_points_per_leg=slippage,
                risk_cap=float(cap), daily_loss_cap=float(daily_cap),
                paper_balance=float(STARTING_BALANCE),
                account_state_checked=False, production_gates_checked=False)


def compare(quotes, now, widths=(25, 50, 100), fee=1.0, slippage=.1):
    """Compare supplied snapshots only; never invent missing wings or fills."""
    groups = {}
    for q in quotes:
        key = (q['symbol'], q['expiration'])
        groups.setdefault(key, []).append(q)
    results = []
    today = now.astimezone(ZoneInfo('America/New_York')).date()
    for (symbol, expiry), rows in sorted(groups.items()):
        dte = (date.fromisoformat(expiry) - today).days
        if not (dte == 1 or 7 <= dte <= 14 or 30 <= dte <= 45):
            results.append(dict(symbol=symbol, expiration=expiry, status='rejected', reasons=['outside_dte_experiment']))
            continue
        lookup = {(q['option_type'], q['strike']): q for q in rows}
        if len(lookup) != len(rows):
            raise ValueError('duplicate contract snapshot')
        puts = [q for q in rows if q['option_type'] == 'put' and .10 <= abs(q['delta']) <= .15]
        calls = [q for q in rows if q['option_type'] == 'call' and .10 <= abs(q['delta']) <= .15]
        pairs = [(p, c) for p, c in itertools.product(puts, calls) if p['strike'] < c['strike']]
        pairs += [(p, lookup[('call', p['strike'])]) for p in rows
                  if p['option_type'] == 'put' and ('call', p['strike']) in lookup
                  and .4 <= abs(p['delta']) <= .6 and .4 <= lookup[('call', p['strike'])]['delta'] <= .6]
        if not pairs:
            results.append(dict(symbol=symbol, expiration=expiry, status='rejected', reasons=['no_matching_short_legs']))
        for p, c in pairs:
            for w in widths:
                lp, lc = lookup.get(('put', p['strike'] - w)), lookup.get(('call', c['strike'] + w))
                if lp is None or lc is None:
                    results.append(dict(symbol=symbol, expiration=expiry, short_strikes=[p['strike'], c['strike']],
                                        width=w, status='rejected', reasons=['missing_exact_wings']))
                else:
                    results.append(evaluate([lp, p, c, lc], now, fee, slippage))
    return sorted(results, key=lambda r: (r['status'] != 'research_candidate', -(r.get('max_profit_after_costs', 0) / max(r.get('max_loss_after_costs', 1), 1))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', help='JSON object with as_of and quotes')
    parser.add_argument('--journal', required=True, help='Append-only research JSONL path')
    parser.add_argument('--ledger', required=True, help='Persistent paper SQLite account ledger')
    args = parser.parse_args()
    with open(args.snapshot) as f:
        snapshot = json.load(f)
    now = datetime.fromisoformat(snapshot['as_of'].replace('Z', '+00:00'))
    if now.tzinfo is None:
        raise ValueError('as_of must include timezone')
    output = compare(snapshot['quotes'], now)
    try:
        from .paper_ledger import PaperLedger
    except ImportError:
        from paper_ledger import PaperLedger
    ledger = PaperLedger(args.ledger)
    output = [ledger.gate(result, snapshot['as_of']) for result in output]
    with open(args.journal, 'a') as f:
        for result in output:
            f.write(json.dumps(result, allow_nan=False) + '\n')
    print(json.dumps({'evaluations': len(output), 'research_candidates': sum(r['status'] == 'research_candidate' for r in output), 'fills': 0}))
