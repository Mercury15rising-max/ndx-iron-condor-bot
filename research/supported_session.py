"""Convert supported-platform Robinhood quote results to offline research input.

No OAuth, credentials, network transport, broker review or execution.
Contract metadata must be supplied from the supported platform's instrument lookup.
"""
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def make_snapshot(contracts, response):
    metadata = {}
    for contract in contracts:
        key = contract['instrument_id']
        if key in metadata:
            raise ValueError('duplicate instrument metadata')
        if contract.get('multiplier') != 100:
            raise ValueError('explicit standard multiplier required')
        if contract['option_type'] not in ('put', 'call'):
            raise ValueError('invalid option type')
        metadata[key] = contract
    data = response.get('structuredContent', response)
    quotes = []
    seen = set()
    for row in data['data']['results'] or []:
        if not row or not row.get('quote'):
            raise ValueError('missing quote')
        q = row['quote']; key = q['instrument_id']
        if key in seen or key not in metadata:
            raise ValueError('duplicate or unmatched quote')
        seen.add(key); c = metadata[key]
        result = {k:c[k] for k in ('symbol','expiration','option_type','multiplier')}
        for dest, value in [('strike',c['strike']),('bid',q['bid_price']),
                            ('ask',q['ask_price']),('delta',q['delta'])]:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError('invalid numeric quote')
            result[dest] = number
        if result['bid'] <= 0 or result['ask'] < result['bid']:
            raise ValueError('missing or crossed market')
        result.update(instrument_id=key, quote_timestamp=q['updated_at'],
                      volume=q['volume'], open_interest=q['open_interest'],
                      bid_size=q.get('bid_size'), ask_size=q.get('ask_size'))
        quotes.append(result)
    if not quotes or seen != set(metadata):
        raise ValueError('incomplete quote set')
    return dict(as_of=datetime.now(timezone.utc).isoformat(), quotes=quotes,
                source='Robinhood supported-platform session', mode='research',
                live_execution_enabled=False)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('contracts', help='JSON list: instrument_id, symbol, expiration, option_type, strike, multiplier')
    parser.add_argument('quotes', help='JSON structured result of get_option_quotes')
    parser.add_argument('output')
    args = parser.parse_args()
    snapshot = make_snapshot(json.loads(Path(args.contracts).read_text()),
                             json.loads(Path(args.quotes).read_text()))
    Path(args.output).write_text(json.dumps(snapshot, indent=2, allow_nan=False))
