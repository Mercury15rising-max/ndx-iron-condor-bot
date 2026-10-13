"""Persistent simulation ledger. No broker calls and no automatic fills."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo
try:
    from .research_risk_policy import STARTING_BALANCE, risk_limits
except ImportError:
    from research_risk_policy import STARTING_BALANCE, risk_limits


def cents(value):
    d = Decimal(str(value))
    if not d.is_finite():
        raise ValueError('nonfinite money')
    return int((d * 100).to_integral_value(rounding=ROUND_CEILING))


def stamp(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('timezone required')
    return t.timestamp(), t.astimezone(ZoneInfo('America/New_York')).date().isoformat()


class PaperLedger:
    def __init__(self, path):
        self.path = path
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY CHECK(id=1), initial INTEGER NOT NULL)')
            db.execute('INSERT OR IGNORE INTO account VALUES (1,?)', (cents(STARTING_BALANCE),))
            db.execute('CREATE TABLE IF NOT EXISTS positions (id TEXT PRIMARY KEY, opened REAL, day TEXT, risk INTEGER, closed REAL, close_day TEXT, pnl INTEGER, evidence TEXT)')

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _state(self, db, when):
        ts, day = stamp(when)
        latest = db.execute('SELECT MAX(COALESCE(closed,opened)) FROM positions').fetchone()[0]
        if latest is not None and ts < latest:
            raise ValueError('cannot evaluate before latest ledger event')
        balance = db.execute('SELECT initial FROM account').fetchone()[0] + db.execute('SELECT COALESCE(SUM(pnl),0) FROM positions').fetchone()[0]
        loss = db.execute('SELECT COALESCE(SUM(-pnl),0) FROM positions WHERE close_day=? AND pnl<0',(day,)).fetchone()[0]
        risk, count = db.execute('SELECT COALESCE(SUM(risk),0),COUNT(*) FROM positions WHERE closed IS NULL').fetchone()
        entries = db.execute('SELECT COUNT(*) FROM positions WHERE day=?',(day,)).fetchone()[0]
        cap, daily = risk_limits(Decimal(balance)/100)
        return dict(balance=balance, daily_loss=loss, open_risk=risk, open_positions=count,
                    entries_today=entries, risk_cap=cents(cap), daily_cap=cents(daily), day=day)

    def _check(self, db, risk, when):
        s = self._state(db, when); reasons=[]
        if risk <= 0 or risk > s['risk_cap']: reasons.append('per_trade_risk')
        if s['open_risk'] + risk > s['risk_cap']: reasons.append('total_open_risk')
        if s['daily_loss'] + s['open_risk'] + risk > s['daily_cap']: reasons.append('daily_loss_budget')
        if s['open_positions'] >= 1 or s['entries_today'] >= 1: reasons.append('position_or_trade_limit')
        return s, reasons

    def check(self, risk, when):
        with self.transaction() as db:
            return self._check(db,cents(risk),when)

    def open_simulation(self, position_id, risk, when, evidence):
        if not position_id or not evidence:
            raise ValueError('position ID and simulation evidence required')
        with self.transaction() as db:
            s, reasons=self._check(db,cents(risk),when)
            if reasons: raise ValueError(','.join(reasons))
            db.execute('INSERT INTO positions VALUES (?,?,?,?,NULL,NULL,NULL,?)',
                       (position_id,stamp(when)[0],s['day'],cents(risk),str(evidence)))

    def close_simulation(self, position_id, net_pnl, when, evidence):
        # net_pnl must include all simulated fees/slippage; no assumed outcome.
        d=Decimal(str(net_pnl))
        if not d.is_finite() or d*100 != (d*100).to_integral_value() or not evidence:
            raise ValueError('cent-precise net P&L and evidence required')
        with self.transaction() as db:
            self._state(db,when)
            row=db.execute('SELECT closed FROM positions WHERE id=?',(position_id,)).fetchone()
            if row is None or row[0] is not None: raise ValueError('not an open position')
            ts,day=stamp(when)
            db.execute('UPDATE positions SET closed=?,close_day=?,pnl=?,evidence=evidence || ? WHERE id=?',
                       (ts,day,int(d*100),'\nCLOSE: '+str(evidence),position_id))

    def gate(self, result, when):
        r=dict(result)
        if 'max_loss_after_costs' not in r: return r
        state,reasons=self.check(r['max_loss_after_costs'],when)
        r['reasons']=sorted(set(r.get('reasons',[])+reasons))
        r.update(account_state_checked=True,paper_account_cents=state)
        if r['reasons']: r['status']='rejected'
        return r
