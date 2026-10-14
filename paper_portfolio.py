"""Serialized, durable shared credit portfolio with recoverable JSON exports.

SQLite is canonical; JSON archives are replayable exports. No broker access.
"""
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile

from exchange_session import NY
from ndx_paper import number, timestamp
from paper_replay import observe, replay

OBSERVED_PORTFOLIO = Path('/workspace/ndxp-state/observed-portfolio.sqlite3')
LIMITS = {'max_risk_per_trade': 500, 'max_daily_loss': 750,
          'max_total_open_risk': 750, 'max_open_positions': 1, 'max_trades_per_day': 1}
PLAN_FIELDS = ('expiration_rule', 'short_strike_rule', 'wing_width_rule',
               'tie_break_rule', 'strategy_rule')


def validate_plan(plan):
    if (not isinstance(plan, dict) or plan.get('mode') != 'explicit_contract_plan'
            or any(not isinstance(plan.get(k), str) or not plan[k].strip() for k in PLAN_FIELDS)):
        raise ValueError('Observed initialization requires explicit_contract_plan and all five selection rules')
    legs = plan.get('legs')
    from credit_paper import ROLES, STRATEGIES
    if (plan.get('strategy') not in STRATEGIES or not isinstance(legs, dict)
            or set(legs) != set(ROLES) or any(not isinstance(i, str) or not i for i in legs.values())
            or len(set(legs.values())) != 4):
        raise ValueError('Selection plan must fix strategy and four distinct contract IDs')
    return plan


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def encoded(archive):
    return json.dumps(archive, sort_keys=True, allow_nan=False).encode()


def export(path, archive):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
            name = out.name
            out.write(encoded(archive)); out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if name and os.path.exists(name): os.unlink(name)


@contextmanager
def locked_portfolio(path):
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        db = sqlite3.connect(path)
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('CREATE TABLE IF NOT EXISTS archives (path TEXT PRIMARY KEY, contents TEXT NOT NULL, exported_hash TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            db.commit()
            yield db
        finally:
            db.close()


def reconcile_exports(db):
    """Repair only recognized pre-commit exports; never overwrite external edits."""
    archives = {}
    for name, contents, exported_hash in db.execute('SELECT path, contents, exported_hash FROM archives'):
        archive = json.loads(contents)
        replay(archive)  # source/config and accounting integrity before export
        path = Path(name)
        actual = file_hash(path)
        current_hash = hashlib.sha256(encoded(archive)).hexdigest()
        if actual == current_hash:
            pass
        elif actual == exported_hash:
            export(path, archive)  # crash after canonical commit, before export
        else:
            raise ValueError(f'Archive export missing/edited outside shared portfolio: {path}')
        db.execute('UPDATE archives SET exported_hash=? WHERE path=?', (current_hash, name))
        archives[name] = archive
    db.commit()
    return archives


def context_for(archives, current, now):
    day = now.astimezone(NY).date().isoformat()
    positions = 0; open_risk = number(0); realized = number(0); entries = 0; cash = number(3000)
    for name, archive in archives.items():
        state, _ = replay(archive)
        cash += number(state['balance'])-3000
        realized += number(state['daily_pnl'].get(day,0))
        entries += sum(e['action']=='PAPER_ENTRY' and timestamp(e['at']).astimezone(NY).date().isoformat()==day for e in state['events'])
        if name != current and state['position']:
            positions += 1
            open_risk += number(state['position']['max_loss'])
    return dict(open_positions=positions, open_risk=str(open_risk), daily_pnl=str(realized),
                trades_today=entries, cash=str(cash))


def apply_observation(db_path, archive_path, archive, snapshot, now, *, initializing=False, plan=None):
    path = Path(archive_path).resolve()
    if path == Path(db_path).resolve() or path == Path(db_path).resolve().with_suffix('.lock'):
        raise ValueError('Archive path must not overwrite portfolio database or lock')
    key = str(path)
    source = snapshot['provenance']['source']
    kind = source['kind']
    if kind == 'observed' and Path(db_path).resolve() != OBSERVED_PORTFOLIO.resolve():
        raise ValueError('Observed credit strategies must use the single bot portfolio')
    if initializing and kind == 'observed':
        validate_plan(plan)
    with locked_portfolio(db_path) as db:
        metadata = dict(db.execute('SELECT key,value FROM metadata'))
        if metadata and metadata['kind'] != kind:
            raise ValueError('Fixture/observed portfolios must remain separate')
        archives = reconcile_exports(db)
        if initializing and key in archives:
            raise ValueError('Archive already registered; reset refused')
        if key in archives:
            archive = archives[key]
            saved_plan = json.loads(metadata.get('plan:'+key, 'null'))
            if plan is not None and plan != saved_plan:
                raise ValueError('Cannot change the frozen selection plan of an existing archive')
            plan = saved_plan
            if plan is not None:
                validate_plan(plan)
        elif archive['records']:
            raise ValueError('Unregistered existing archive: preserve it and audit/register under its original code; automatic adoption refused')
        elif not initializing:
            raise ValueError('Missing portfolio registration; --init required for a genuinely new archive')
        risk = archive['config']['risk']
        # The task's verified limits cannot be loosened by env or an archive.
        if any(number(risk[k]) != number(v) for k,v in LIMITS.items()):
            raise ValueError('Credit archive risk differs from verified shared bot limits')
        strategy = archive['config']['strategy']
        current_state, _ = replay(archive)
        if current_state['position'] is None and snapshot['provenance'].get('history_unavailable'):
            raise ValueError('Entry requires validated three-session history after recovery')
        fixed_rules=archive['config'].get('selection_rules')
        if kind=='observed' and strategy=='iron_condor' and fixed_rules!='fixed_ndxp_condor_v1':
            raise ValueError('Observed first condor experiment requires fixed_ndxp_condor_v1')
        if fixed_rules and current_state['position'] is None:
            from condor_selection import select_condor
            if plan is not None and plan.get('ruleset')!=fixed_rules:
                raise ValueError('Plan must have been validated against the fixed condor rules')
            try:
                snapshot=dict(snapshot,selection=select_condor(snapshot,now))
            except (ValueError,KeyError,TypeError):
                pass  # engine records the precise NO_TRADE reason; never substitute
        if plan is not None and (plan['strategy'] != strategy or snapshot.get('selection', {}).get('legs') != plan['legs']):
            state, _ = replay(archive)
            if state['position'] is None:
                if fixed_rules:
                    snapshot=dict(snapshot,selection_rejection='Rule-selected IDs differ from validated first-experiment plan')
                else:
                    raise ValueError('Entry selection differs from frozen explicit contract plan')
        last = metadata.get('last_observed')
        if last and now < timestamp(last):
            raise ValueError('Observations across strategies must be globally chronological')
        archives[key] = archive
        snapshot = dict(snapshot, portfolio_context=context_for(archives,key,now), selection_plan=plan)
        updated = observe(archive,snapshot,now)
        state, report = replay(updated)
        before_hash = file_hash(path)
        # Commit canonical state first; crash recovery exports it exactly once.
        db.execute('INSERT OR REPLACE INTO archives VALUES (?,?,?)', (key,encoded(updated).decode(),before_hash))
        for mk,mv in {'kind':kind, 'last_observed':now.isoformat(), 'plan:'+key:json.dumps(plan)}.items():
            db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',(mk,mv))
        db.commit()
        export(path,updated)
        db.execute('UPDATE archives SET exported_hash=? WHERE path=?',(file_hash(path),key))
        db.commit()
        archives[key] = updated
        report['shared_portfolio'] = dict(context_for(archives,'',now), database=str(Path(db_path).resolve()))
        return updated, state, report
