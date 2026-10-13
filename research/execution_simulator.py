"""Persistent offline package execution simulator. No network or broker transport."""
import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal


class ExecutionSimulator:
    def __init__(self, path):
        self.path = str(path)
        with self.tx() as db:
            db.execute('CREATE TABLE IF NOT EXISTS sim_state (id INTEGER PRIMARY KEY, payload TEXT)')
            db.execute('INSERT OR IGNORE INTO sim_state VALUES (1,?)', (json.dumps(dict(
                phase='flat', active=None, quantity=0, halted=False, sequence=0)),))
            db.execute('CREATE TABLE IF NOT EXISTS sim_events (id TEXT PRIMARY KEY, payload TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS sim_orders (id TEXT PRIMARY KEY)')

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute('BEGIN IMMEDIATE'); yield db; db.commit()
        except Exception:
            db.rollback(); raise
        finally:
            db.close()

    def state(self):
        with self.tx() as db:
            return json.loads(db.execute('SELECT payload FROM sim_state WHERE id=1').fetchone()[0])

    def apply(self, event_id, kind, **data):
        if not event_id: raise ValueError('Event ID required')
        payload = json.dumps(dict(kind=kind, data=data), sort_keys=True, allow_nan=False)
        with self.tx() as db:
            prior = db.execute('SELECT payload FROM sim_events WHERE id=?',(event_id,)).fetchone()
            if prior:
                if prior[0] != payload: raise ValueError('Conflicting duplicate event')
                return json.loads(db.execute('SELECT payload FROM sim_state WHERE id=1').fetchone()[0])
            s = json.loads(db.execute('SELECT payload FROM sim_state WHERE id=1').fetchone()[0])
            if kind == 'halt':
                s['halted'] = True
            elif kind in ('submit_entry', 'submit_exit'):
                entering = kind == 'submit_entry'
                if s['active'] is not None: raise ValueError('Unresolved order blocks submission')
                if entering and (s['halted'] or s['phase'] != 'flat'):
                    raise ValueError('Entry blocked')
                if not entering and s['quantity'] <= 0: raise ValueError('Nothing to exit')
                qty = data['quantity']
                if type(qty) is not int or qty <= 0: raise ValueError('Positive integer quantity required')
                if entering:
                    risk = Decimal(str(data['max_loss_after_costs']))
                    if not risk.is_finite() or not 0 < risk <= 30 or qty != 1:
                        raise ValueError('Entry risk or one-package limit')
                elif qty > s['quantity']: raise ValueError('Exit exceeds position')
                oid = data['order_id']
                if not isinstance(oid,str) or not oid: raise ValueError('Order ID required')
                db.execute('INSERT INTO sim_orders VALUES (?)',(oid,))
                s['active'] = dict(id=oid, side='entry' if entering else 'exit', requested=qty, filled=0)
                s['phase'] = 'pending'
            elif kind == 'timeout':
                if not s['active'] or data['order_id'] != s['active']['id']:
                    raise ValueError('Unknown order')
                s['phase'] = 'unknown'
            elif kind == 'report':
                order = s['active']
                if not order or order['id'] != data['order_id']: raise ValueError('Unknown order')
                if not data.get('evidence'): raise ValueError('Synthetic report evidence required')
                status = data['status']; filled = data['cumulative_filled']
                if status not in ('working','partial','filled','rejected','canceled'):
                    raise ValueError('Invalid status')
                if type(filled) is not int or not order['filled'] <= filled <= order['requested']:
                    raise ValueError('Invalid or regressing fill total')
                if status == 'filled' and filled != order['requested']: raise ValueError('Incomplete fill')
                if status == 'rejected' and filled != 0: raise ValueError('Rejected with fills')
                if status == 'partial' and not 0 < filled < order['requested']:
                    raise ValueError('Invalid package partial fill')
                delta = filled - order['filled']
                s['quantity'] += delta if order['side']=='entry' else -delta
                order['filled'] = filled
                if status in ('filled','rejected','canceled'):
                    s['active'] = None
                    s['phase'] = 'open' if s['quantity'] else 'flat'
                else: s['phase'] = 'pending'
            elif kind == 'leg_mismatch':
                # A one-lot package cannot have fractional package fills. Legging
                # exposure requires independent reconciliation, never automatic retry.
                s['halted'] = True; s['phase'] = 'reconciliation_required'
            else: raise ValueError('Unknown event')
            s['sequence'] += 1
            db.execute('UPDATE sim_state SET payload=? WHERE id=1',(json.dumps(s),))
            db.execute('INSERT INTO sim_events VALUES (?,?)',(event_id,payload))
            return s
