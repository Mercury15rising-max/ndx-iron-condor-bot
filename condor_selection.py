"""Fixed NDXP condor rules; deterministic rejection, never contract substitution."""
from copy import deepcopy
from datetime import date

from exchange_session import NY, bounds
from ndx_paper import number, usable_quote

RULESET = 'fixed_ndxp_condor_v1'


def select_condor(snapshot, now):
    if snapshot.get('complete') is not True:
        raise ValueError('Complete instrument/quote universe required')
    chains = snapshot.get('chains', [])
    instruments = snapshot.get('instruments', [])
    quotes = snapshot.get('quotes', [])
    for rows, key in ((chains,'id'), (instruments,'id'), (quotes,'instrument_id')):
        if not isinstance(rows,list) or any(not isinstance(r,dict) or not isinstance(r.get(key),str) or not r[key] for r in rows):
            raise ValueError('Malformed or missing contract/quote IDs')
        if len({r[key] for r in rows}) != len(rows):
            raise ValueError('Duplicate instrument, chain or quote IDs')
    eligible_chains = {c['id'] for c in chains if c.get('symbol')=='NDXP'
                       and c.get('settle_on_open') is False and c.get('can_open_position') is True
                       and number(c['trade_value_multiplier'])==100}
    candidates = []; seen = set()
    today = now.astimezone(NY).date()
    for i in instruments:
        if i.get('chain_id') not in eligible_chains or i.get('chain_symbol')!='NDXP':
            continue
        if i.get('state')!='active' or i.get('tradability')!='tradable':
            continue
        if i.get('type') not in ('put','call') or number(i['trade_value_multiplier'])!=100:
            raise ValueError('Invalid NDXP contract metadata')
        expiry = date.fromisoformat(i['expiration_date'])
        strike = number(i['strike_price'])
        if strike<=0: raise ValueError('Invalid strike')
        key = (i['chain_id'],expiry,i['type'],strike)
        if key in seen: raise ValueError('Ambiguous contracts at same chain/expiry/type/strike')
        seen.add(key)
        if 1 <= (expiry-today).days <= 7 and bounds(expiry) is not None:
            candidates.append(i)
    if not candidates: raise ValueError('No PM-settled NDXP expiration within 1–7 days')
    expiry = min(date.fromisoformat(i['expiration_date']) for i in candidates)
    candidates = [i for i in candidates if date.fromisoformat(i['expiration_date'])==expiry]
    if len({i['chain_id'] for i in candidates})!=1:
        raise ValueError('Multiple PM chains at earliest expiration; no chain substitution')
    by_quote = {q['instrument_id']:q for q in quotes}
    qualifying = {'put':[], 'call':[]}
    for i in candidates:
        q = by_quote.get(i['id'])
        if q is None or 'delta' not in q:
            raise ValueError('Missing delta prevents complete short-leg ranking')
        delta = abs(number(q['delta']))
        if delta>1: raise ValueError('Invalid option delta')
        if number('0.10') <= delta <= number('0.15'):
            qualifying[i['type']].append(i)
    if not all(qualifying.values()): raise ValueError('No shorts in inclusive absolute delta range .10–.15')
    sp = max(qualifying['put'],key=lambda i:number(i['strike_price']))
    sc = min(qualifying['call'],key=lambda i:number(i['strike_price']))
    if number(sp['strike_price'])>=number(sc['strike_price']):
        raise ValueError('Invalid condor short strike ordering')
    def wing(kind, strike):
        matches = [i for i in candidates if i['type']==kind and number(i['strike_price'])==strike]
        if len(matches)!=1: raise ValueError('Exact symmetric 25-point protective wings unavailable')
        return matches[0]
    lp = wing('put',number(sp['strike_price'])-25)
    lc = wing('call',number(sc['strike_price'])+25)
    legs = dict(long_put=lp,short_put=sp,short_call=sc,long_call=lc)
    if any(not usable_quote(by_quote.get(i['id'],{}),now) for i in legs.values()):
        raise ValueError('Selected legs require original fresh uncrossed quotes and sizes >=1')
    return dict(strategy='iron_condor',legs={role:i['id'] for role,i in legs.items()})


def make_plan(snapshot, now):
    selection = select_condor(snapshot,now)
    if snapshot.get('provenance',{}).get('source',{}).get('kind')!='observed':
        raise ValueError('Plan creation requires actual observed-market provenance; fixtures refused')
    return dict(mode='explicit_contract_plan', strategy='iron_condor', legs=selection['legs'],
                ruleset=RULESET,
                expiration_rule='Earliest available PM-settled NDXP expiry within 1–7 calendar days; no 0DTE',
                short_strike_rule='Absolute delta .10–.15 inclusive; highest qualifying put strike and lowest qualifying call strike',
                wing_width_rule='Exactly 25 points outside each short; symmetric; no substitution',
                tie_break_rule='Reject duplicate IDs, ambiguous same chain/expiry/type/strike and multiple PM chains at earliest expiry; order independent',
                strategy_rule='Iron condor only; no butterfly fallback')


def main():
    import argparse, json, os
    from datetime import datetime, timezone
    from pathlib import Path
    from paper_pipeline import build_snapshot
    from paper_portfolio import (OBSERVED_PORTFOLIO, locked_portfolio, reconcile_exports,
                                 context_for, validate_plan, LIMITS)
    from paper_replay import new_archive
    from ndx_paper import initial_state, step, timestamp
    parser=argparse.ArgumentParser(description='Validate actual exported data before creating a fixed condor plan; no archive initialization')
    parser.add_argument('bundle',type=Path)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--historical',action='store_true')
    args=parser.parse_args()
    if (os.getenv('TRADING_MODE','paper').lower()!='paper' or os.getenv('ROBINHOOD_LIVE_ORDERS','false').lower()!='false'
            or os.getenv('ALLOW_0DTE','false').lower()!='false'):
        parser.error('Paper mode; live orders and 0DTE disabled required')
    bundle=json.loads(args.bundle.read_text()); now=timestamp(bundle['observed_at'])
    if not args.historical and not 0 <= (datetime.now(timezone.utc)-now).total_seconds() <=60:
        parser.error('Use --historical for actual historical exports; retain original timestamps')
    if bundle.get('source',{}).get('kind')!='observed':
        parser.error('Actual observed data required; fixtures cannot create a plan')
    snapshot=build_snapshot(bundle,now)
    config=new_archive('iron_condor',selection_rules=RULESET)['config']
    if any(number(config['risk'][k])!=number(v) for k,v in LIMITS.items()):
        parser.error('Configuration differs from the five verified shared portfolio limits')
    if OBSERVED_PORTFOLIO.exists():
        with locked_portfolio(OBSERVED_PORTFOLIO) as db:
            archives=reconcile_exports(db)
            metadata=dict(db.execute('SELECT key,value FROM metadata'))
            if metadata.get('last_observed') and now < timestamp(metadata['last_observed']):
                parser.error('Historical observation predates shared portfolio state')
            snapshot['portfolio_context']=context_for(archives,'',now)
    try:
        plan=make_plan(snapshot,now)
        state,event=step(initial_state(),snapshot,now,**config)
        if event['action']!='PAPER_ENTRY':
            print(json.dumps({'action':'NO_TRADE','reason':event['reason']})); return
    except (ValueError,KeyError,TypeError) as error:
        print(json.dumps({'action':'NO_TRADE','reason':str(error)})); return
    validate_plan(plan)
    args.plan.parent.mkdir(parents=True,exist_ok=True)
    with args.plan.open('x') as out:
        json.dump(plan,out,indent=2,allow_nan=False)
    print(json.dumps({'action':'PLAN_VALIDATED','plan':str(args.plan),
                      'max_loss':state['position']['max_loss'],
                      'note':'Validation only; no archive or paper trade created'}))


if __name__=='__main__':
    main()
