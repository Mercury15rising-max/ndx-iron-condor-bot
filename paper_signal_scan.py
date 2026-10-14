"""Read-only watchlist signal evaluation; does not simulate fills or place orders."""
import argparse
import json
from datetime import datetime
from ema_signals import evaluate_ema, evaluate_setup
from research_watchlist import DEFAULT_RESEARCH_WATCHLIST
from session_bars import normalize_robinhood


def scan(snapshot, now):
    calendar = snapshot['signal_calendar']
    rows = snapshot['series']
    by_symbol = {r['symbol']: r for r in rows}
    if len(by_symbol) != len(rows):
        raise ValueError('Duplicate series symbols')
    output=[]
    for asset in DEFAULT_RESEARCH_WATCHLIST:
        row={'symbol':asset.symbol, 'role':asset.role, 'execution':'NOT_ENABLED'}
        try:
            bars=normalize_robinhood(by_symbol[asset.symbol],now)
            row['ema']=evaluate_ema(bars,now,symbol=asset.symbol,session_calendar=calendar)
            row['rollback']=evaluate_setup(bars,now,symbol=asset.symbol,mode='ema9_rollback',session_calendar=calendar)
            row['vwap']=evaluate_setup(bars,now,symbol=asset.symbol,mode='vwap_flip',session_start=snapshot.get('signal_session_start'),session_calendar=calendar)
        except (ValueError,KeyError,TypeError) as error:
            row['error']=str(error)
        output.append(row)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot')
    parser.add_argument('--observed-at',required=True)
    args=parser.parse_args()
    now=datetime.fromisoformat(args.observed_at)
    if now.tzinfo is None: parser.error('Timezone-aware observation required')
    with open(args.snapshot) as f: snapshot=json.load(f)
    print(json.dumps(scan(snapshot,now),indent=2,allow_nan=False))


if __name__=='__main__': main()
