"""Explicit snapshot fill assumptions and paper accounting; no broker orders."""
import json
import math
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from paper_strategy_lab import evaluate
from paper_ledger import PaperLedger, stamp


def money(value):
    return Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)


def identity(q):
    return (q['instrument_id'], q['symbol'],q['expiration'],q['option_type'],q['strike'],q['multiplier'])


def prices(legs, now, exiting, fee=1.0, slippage=.1):
    if now.tzinfo is None or len(legs)!=4: raise ValueError('Four legs and aware timestamp required')
    if any(not math.isfinite(float(x)) or x<0 for x in (fee,slippage)):
        raise ValueError('Invalid costs')
    keys=[identity(q) for q in legs]
    if len({k[0] for k in keys})!=4: raise ValueError('Duplicate instrument')
    if len({(q['symbol'],q['expiration']) for q in legs})!=1:
        raise ValueError('Mixed underlying or expiry')
    if [q['option_type'] for q in legs]!=['put','put','call','call']:
        raise ValueError('Expected long put, short put, short call, long call')
    amounts=[]
    for i,q in enumerate(legs):
        if q['multiplier']!=100: raise ValueError('Unsupported multiplier')
        bid,ask=float(q['bid']),float(q['ask'])
        if not all(math.isfinite(v) for v in (bid,ask)) or bid<=0 or ask<bid:
            raise ValueError('Unavailable or crossed market')
        t=datetime.fromisoformat(q['quote_timestamp'].replace('Z','+00:00'))
        if t.tzinfo is None or not -2<=(now-t).total_seconds()<=30:
            raise ValueError('Stale or future quote')
        buy=(i in (0,3)) != exiting
        size=q.get('ask_size' if buy else 'bid_size')
        if type(size) is not int or size<1: raise ValueError('Missing displayed size')
        px=Decimal(str(ask if buy else bid))+(Decimal(str(slippage)) if buy else -Decimal(str(slippage)))
        if px<=0: raise ValueError('Nonpositive assumed fill')
        amounts.append((-px if buy else px)*100)
    return money(sum(amounts)-Decimal(str(fee))*4)


class PricedPaperLedger(PaperLedger):
    def __init__(self,path):
        super().__init__(path)
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS priced_positions '
                       '(id TEXT PRIMARY KEY, contracts TEXT, entry_cash TEXT, fee REAL, slip REAL)')

    def enter(self,position_id,legs,now,fee=1.,slippage=.1):
        result=evaluate(legs,now,fee,slippage)
        if result['status']!='research_candidate': raise ValueError(','.join(result['reasons']))
        cash=prices(legs,now,False,fee,slippage)
        encoded=json.dumps([identity(q) for q in legs],allow_nan=False)
        when=now.isoformat()
        with self.transaction() as db:
            from paper_ledger import cents
            s,reasons=self._check(db,cents(result['max_loss_after_costs']),when)
            if reasons: raise ValueError(','.join(reasons))
            db.execute('INSERT INTO positions VALUES (?,?,?,?,NULL,NULL,NULL,?)',
                (position_id,stamp(when)[0],s['day'],cents(result['max_loss_after_costs']),
                 json.dumps({'assumption':'synthetic simultaneous four-leg fill; not confirmed executable',
                             'entry_cash':str(cash),'quotes':legs},allow_nan=False)))
            db.execute('INSERT INTO priced_positions VALUES (?,?,?,?,?)',
                       (position_id,encoded,str(cash),fee,slippage))
        return dict(position_id=position_id,simulated=True,entry_cash=float(cash),risk=result['max_loss_after_costs'])

    def mark(self,position_id,legs,now):
        with self.transaction() as db:
            self._state(db,now.isoformat())
            row=db.execute('SELECT p.closed,x.contracts,x.entry_cash,x.fee,x.slip FROM positions p '
                'JOIN priced_positions x ON p.id=x.id WHERE p.id=?',(position_id,)).fetchone()
            if not row or row[0] is not None: raise ValueError('Not an open priced position')
            if json.loads(row[1])!=[list(identity(q)) for q in legs]: raise ValueError('Contract mismatch')
            exit_cash=prices(legs,now,True,row[3],row[4])
            net=money(Decimal(row[2])+exit_cash)
            return dict(position_id=position_id,simulated=True,net_pnl=float(net),exit_cash=float(exit_cash),
                        as_of=now.isoformat(),quotes=legs)

    def exit(self,position_id,legs,now):
        mark=self.mark(position_id,legs,now)
        # close_simulation atomically refuses duplicate closes and chronological regressions.
        self.close_simulation(position_id,mark['net_pnl'],now.isoformat(),
                              json.dumps(mark,allow_nan=False))
        return mark

    def exit_signal(self,position_id,legs,now,profit_target,loss_limit):
        if any(not math.isfinite(float(x)) or x<=0 for x in (profit_target,loss_limit)):
            raise ValueError('Explicit positive dollar thresholds required')
        mark=self.mark(position_id,legs,now)
        mark['signal']='take_profit' if mark['net_pnl']>=profit_target else ('stop_loss' if mark['net_pnl']<=-loss_limit else 'hold')
        return mark
