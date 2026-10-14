"""Four-leg NDXP credit-position simulation. No brokerage or order access."""
from copy import deepcopy
from datetime import date, time, timedelta
from decimal import InvalidOperation

from config import SETTINGS
from exchange_session import NY, bounds, session_at
from ndx_paper import number, timestamp, fresh, usable_quote

ROLES = ('long_put', 'short_put', 'short_call', 'long_call')
STRATEGIES = ('iron_condor', 'iron_butterfly')
RISK_FIELDS = ('max_risk_per_trade', 'max_daily_loss', 'max_open_positions',
               'max_trades_per_day', 'max_total_open_risk', 'max_positions_per_family',
               'profit_target_pct', 'stop_loss_multiple', 'normal_entry_start',
               'normal_entry_end', 'exit_only_start')


def configured_risk():
    return {key: getattr(SETTINGS, key) for key in RISK_FIELDS}


def validate_risk(risk, fee):
    if not isinstance(risk, dict) or set(risk) != set(RISK_FIELDS):
        raise ValueError('Incomplete credit risk configuration')
    for key in RISK_FIELDS[:6]:
        if number(risk[key]) < 0:
            raise ValueError('Negative risk limit')
    if not 0 < number(risk['profit_target_pct']) <= 100 or number(risk['stop_loss_multiple']) <= 1:
        raise ValueError('Invalid credit exit thresholds')
    for key in RISK_FIELDS[8:]:
        time.fromisoformat(risk[key])
    if number(fee) < 0:
        raise ValueError('Negative fee')


def quote_map(rows):
    if not isinstance(rows, list) or any(not isinstance(q, dict) for q in rows):
        raise ValueError('Malformed quotes')
    ids = [q.get('instrument_id') for q in rows]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Missing/duplicate quote IDs')
    return dict(zip(ids, rows))


def selected_legs(snapshot, strategy, now):
    selection = snapshot.get('selection', {})
    if not isinstance(selection, dict):
        raise ValueError('Malformed strategy selection')
    ids = selection.get('legs', {})
    if selection.get('strategy') != strategy or not isinstance(ids, dict) or set(ids) != set(ROLES):
        raise ValueError('Explicit matching four-leg strategy selection required')
    if any(not isinstance(i, str) or not i for i in ids.values()) or len(set(ids.values())) != 4:
        raise ValueError('Four distinct instrument IDs required')
    instruments = snapshot.get('instruments', [])
    chains = snapshot.get('chains', [])
    for rows in (instruments, chains):
        if not isinstance(rows, list) or any(not isinstance(i, dict) or not isinstance(i.get('id'), str) for i in rows):
            raise ValueError('Malformed contract metadata')
        if len({i['id'] for i in rows}) != len(rows):
            raise ValueError('Duplicate metadata IDs')
    by_id = {i['id']: i for i in instruments}
    legs = {role: by_id[ids[role]] for role in ROLES}
    chain_ids = {i['chain_id'] for i in legs.values()}
    expirations = {i['expiration_date'] for i in legs.values()}
    if len(chain_ids) != 1 or len(expirations) != 1:
        raise ValueError('All four legs must share chain and expiration')
    chain = next(c for c in chains if c['id'] == next(iter(chain_ids)))
    if (chain.get('symbol') != 'NDXP' or chain.get('settle_on_open') is not False
            or chain.get('can_open_position') is not True or number(chain['trade_value_multiplier']) != 100):
        raise ValueError('Eligible PM-settled NDXP chain required')
    expiry = date.fromisoformat(next(iter(expirations)))
    if expiry <= now.astimezone(NY).date() or bounds(expiry) is None:
        raise ValueError('Future exchange-session expiry required; 0DTE disabled')
    strikes = []
    for role, i in legs.items():
        if (i['chain_symbol'] != 'NDXP' or i['type'] != ('put' if 'put' in role else 'call')
                or i['state'] != 'active' or i['tradability'] != 'tradable'
                or number(i['trade_value_multiplier']) != 100):
            raise ValueError('Ineligible leg metadata')
        strikes.append(number(i['strike_price']))
    lp, sp, sc, lc = strikes
    if not 0 < lp < sp <= sc < lc or (strategy == 'iron_condor' and sp == sc) or (strategy == 'iron_butterfly' and sp != sc):
        raise ValueError('Invalid strike ordering or protective wings')
    return deepcopy(legs), max(sp-lp, lc-sc)*100


def entry_credit(legs, quotes):
    return sum((number(quotes[legs[r]['id']]['bid_price']) if r.startswith('short')
                else -number(quotes[legs[r]['id']]['ask_price'])) for r in ROLES)*100


def close_debit(legs, quotes):
    return sum((number(quotes[legs[r]['id']]['ask_price']) if r.startswith('short')
                else -number(quotes[legs[r]['id']]['bid_price'])) for r in ROLES)*100


def step(state, snapshot, now, *, strategy, risk, fee_per_contract):
    validate_risk(risk, fee_per_contract)
    if strategy not in STRATEGIES or state.get('engine') != 'ndxp_v1' or state.get('version') != 1:
        raise ValueError('Unsupported strategy/state')
    if now.tzinfo is None or (state['last_observed'] and now <= timestamp(state['last_observed'])):
        raise ValueError('Timezone-aware advancing observation required')
    state = deepcopy(state)
    state['last_observed'] = now.isoformat()
    def finish(action, reason, **details):
        event = dict(at=now.isoformat(), action=action, reason=reason, paper_only=True, **details)
        state['events'].append(event)
        return state, event
    position = state['position']
    unresolved = 'UNRESOLVED' if position else 'NO_TRADE'
    session = session_at(now)
    if session is None or snapshot.get('session_open') is not True or not fresh(snapshot.get('session_observed_at'), now):
        return finish(unresolved, 'Verified open regular session required')
    try:
        quotes = quote_map(snapshot.get('quotes', []))
        if position:
            if position.get('strategy') != strategy:
                raise ValueError('Open position strategy mismatch')
            legs = position['legs']
        else:
            legs, width_cash = selected_legs(snapshot, strategy, now)
        for leg in legs.values():
            q = quotes.get(leg['id'], {})
            if not usable_quote(q, now):
                raise ValueError('All four fresh positive uncrossed quotes with sizes >=1 required')
            if position and timestamp(q['updated_at']) <= timestamp(position['opened_at']):
                raise ValueError('Exit quotes must be newer than entry')
    except (KeyError, ValueError, TypeError, InvalidOperation, StopIteration) as error:
        return finish(unresolved, str(error))
    selected_quotes = {i['id']: deepcopy(quotes[i['id']]) for i in legs.values()}
    fee = number(fee_per_contract)*4  # one contract per leg, every modeled side
    day = session['date']
    portfolio = snapshot.get('portfolio_context')
    if portfolio is not None and (not isinstance(portfolio, dict) or set(portfolio) != {'open_positions','open_risk','daily_pnl','trades_today','cash'}):
        raise ValueError('Malformed shared portfolio context')
    daily_pnl = number(portfolio['daily_pnl']) if portfolio else number(state['daily_pnl'].get(day,0))
    if position:
        gross = close_debit(legs, quotes)
        cost = gross + number(position['exit_fee'])
        net_entry = number(position['net_entry_credit'])
        pnl = net_entry-cost
        stop = number(position['gross_entry_credit'])*number(risk['stop_loss_multiple'])
        target = number(position['gross_entry_credit'])*(1-number(risk['profit_target_pct'])/100)
        local_time = now.astimezone(NY).time()
        action = ('KILL_SWITCH' if daily_pnl <= -number(risk['max_daily_loss'])
                  else 'STOP_LOSS' if gross >= stop
                  else 'TAKE_PROFIT' if gross <= target
                  else 'TIME_EXIT' if (local_time >= time.fromisoformat(risk['exit_only_start'])
                                      or now >= timestamp(session['close'])-timedelta(minutes=30))
                  else 'HOLD')
        details = dict(position=position, quotes=selected_quotes, gross_exit_debit=str(gross),
                       exit_fee=position['exit_fee'], exit_cost=str(cost), net_pnl=str(pnl),
                       stop_debit=str(stop), profit_target_debit=str(target))
        if action != 'HOLD':
            state['balance'] = str(number(state['balance'])-cost)
            state['daily_pnl'][day] = str(number(state['daily_pnl'].get(day,0))+pnl)
            state['position'] = None
            state['completed'] += 1
        return finish(action, 'Whole-position quote-side credit valuation; modeled fees included', **details)
    local_time = now.astimezone(NY).time()
    if not time.fromisoformat(risk['normal_entry_start']) <= local_time < min(time.fromisoformat(risk['normal_entry_end']), time.fromisoformat(risk['exit_only_start'])):
        return finish('NO_TRADE', 'Outside configured entry window')
    if snapshot.get('complete') is not True:
        return finish('NO_TRADE', 'Complete contract/quote universe required')
    entries = sum(e['action']=='PAPER_ENTRY' and timestamp(e['at']).astimezone(NY).date().isoformat()==day for e in state['events'])
    if portfolio:
        entries = number(portfolio['trades_today'])
    other_positions = number(portfolio['open_positions']) if portfolio else number(0)
    if (entries >= number(risk['max_trades_per_day']) or other_positions >= number(risk['max_open_positions'])
            or number(risk['max_positions_per_family']) < 1
            or daily_pnl <= -number(risk['max_daily_loss'])):
        return finish('NO_TRADE', 'Configured daily/position risk limit reached')
    if state['completed'] >= 30:
        return finish('COMPLETE', '30 completed trades; review required')
    gross = entry_credit(legs, quotes)
    net = gross-fee
    maximum_loss = width_cash-gross+fee*2
    if gross <= 0 or gross >= width_cash or net <= 0:
        return finish('NO_TRADE', 'Invalid fee-inclusive credit relative to protective width')
    cash = number(portfolio['cash']) if portfolio else number(state['balance'])
    total_risk = number(portfolio['open_risk']) if portfolio else number(0)
    if maximum_loss > min(number(risk['max_risk_per_trade']), number(risk['max_total_open_risk'])-total_risk, cash):
        return finish('NO_TRADE', 'Fee-inclusive maximum loss exceeds configured risk/cash limits', max_loss=str(maximum_loss))
    position = dict(strategy=strategy, legs=legs, entry_quotes=selected_quotes,
                    opened_at=now.isoformat(), quantity=1, multiplier=100,
                    gross_entry_credit=str(gross), net_entry_credit=str(net), entry_fee=str(fee),
                    exit_fee=str(fee), max_loss=str(maximum_loss), maximum_width_cash=str(width_cash))
    state['position'] = position
    state['balance'] = str(number(state['balance'])+net)
    return finish('PAPER_ENTRY', 'Hypothetical four-leg quote model, not broker fills', position=position)
