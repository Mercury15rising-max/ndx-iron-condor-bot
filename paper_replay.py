"""Auditable NDX paper observations. No network or brokerage access."""
import argparse
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile
from importlib.metadata import version

import ndx_paper


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def implementation():
    root = Path(__file__).parent
    return digest({"sources": {p: (root / p).read_text() for p in
                   ("ndx_paper.py", "credit_paper.py", "paper_portfolio.py", "ema_signals.py", "exchange_session.py", "paper_replay.py")},
                   "calendar_version": version("exchange-calendars")})


def new_archive(strategy="call_debit_spread", fee_per_contract="0.50"):
    config = {"entry_signal": "triple_cross"}
    if strategy != "call_debit_spread":
        from credit_paper import STRATEGIES, configured_risk, validate_risk
        if strategy not in STRATEGIES:
            raise ValueError("Unknown credit strategy")
        config = {"strategy": strategy, "risk": configured_risk(), "fee_per_contract": str(fee_per_contract)}
        validate_risk(config["risk"], config["fee_per_contract"])
    return {"version": 1, "implementation": implementation(),
            "config": config, "records": []}


def accounting(state):
    """Independent cash reconciliation from recorded quote-side prices."""
    cash = Decimal(3000)
    opened = None
    pnls = []
    peak = cash
    drawdown = Decimal(0)
    daily = {}
    position = None
    stress = Decimal(0)
    for event in state["events"]:
        action = event["action"]
        if action == "PAPER_ENTRY":
            if opened is not None:
                raise ValueError("Overlapping entries")
            p = event["position"]
            position = p
            if p.get("strategy") in ("iron_condor", "iron_butterfly"):
                gross = sum(Decimal(str(p['entry_quotes'][i['id']]['bid_price' if r.startswith('short') else 'ask_price']))
                            * (1 if r.startswith('short') else -1) for r,i in p['legs'].items())*100
                fee = Decimal(p['entry_fee'])
                net = gross-fee
                if fee < 0 or Decimal(p['exit_fee']) < 0 or gross != Decimal(p['gross_entry_credit']) or net != Decimal(p['net_entry_credit']):
                    raise ValueError('Credit entry accounting mismatch')
                strikes = {r: Decimal(i['strike_price']) for r,i in p['legs'].items()}
                width = max(strikes['short_put']-strikes['long_put'], strikes['long_call']-strikes['short_call'])*100
                if width-gross+fee+Decimal(p['exit_fee']) != Decimal(p['max_loss']):
                    raise ValueError('Credit maximum-loss accounting mismatch')
                opened = -net
            else:
                opened = (Decimal(str(p["long_quote"]["ask_price"])) -
                          Decimal(str(p["short_quote"]["bid_price"]))) * 100 + 2
                if opened != Decimal(p["entry_cost"]):
                    raise ValueError("Entry accounting mismatch")
            cash -= opened
        elif action in ("STOP_LOSS", "TIME_EXIT", "TAKE_PROFIT", "KILL_SWITCH"):
            if opened is None:
                raise ValueError("Exit without entry")
            if event["position"] != position:
                raise ValueError("Exit position mismatch")
            credit = position.get('strategy') in ('iron_condor', 'iron_butterfly')
            if credit:
                gross = sum(Decimal(str(event['quotes'][i['id']]['ask_price' if r.startswith('short') else 'bid_price']))
                            * (1 if r.startswith('short') else -1) for r,i in position['legs'].items())*100
                value = -(gross+Decimal(position['exit_fee']))
                if gross != Decimal(event['gross_exit_debit']) or -value != Decimal(event['exit_cost']) or event['exit_fee'] != position['exit_fee']:
                    raise ValueError('Credit exit accounting mismatch')
            else:
                value = (Decimal(str(event["long_quote"]["bid_price"])) -
                         Decimal(str(event["short_quote"]["ask_price"]))) * 100 - 2
            pnl = value - opened
            if (not credit and value != Decimal(event["exit_value"])) or pnl != Decimal(event["net_pnl"]):
                raise ValueError("Exit accounting mismatch")
            cash += value
            pnls.append(pnl)
            stress += 40 if credit else 20
            day = ndx_paper.timestamp(event["at"]).astimezone(ndx_paper.CT).date().isoformat()
            daily[day] = daily.get(day, Decimal(0)) + pnl
            opened = None
            position = None
            peak = max(peak, cash)
            drawdown = max(drawdown, peak - cash)
    if cash != Decimal(state["balance"]) or len(pnls) != state["completed"]:
        raise ValueError("Ledger reconciliation failed")
    if (opened is None) != (state["position"] is None):
        raise ValueError("Open-position reconciliation failed")
    if position != state["position"] or daily != {day: Decimal(value) for day, value in state["daily_pnl"].items()}:
        raise ValueError("Position/daily P&L reconciliation failed")
    total = sum(pnls, Decimal(0))
    count = len(pnls)
    return {"completed_trades": count, "realized_pnl": str(total),
            "mean_net_pnl": str(total / count) if count else None,
            "win_rate": str(Decimal(sum(p > 0 for p in pnls)) / count) if count else None,
            "closed_trade_max_drawdown": str(drawdown), "cash": str(cash),
            "unresolved_position": opened is not None,
            "goal": "REVIEW_REQUIRED" if count >= 30 and opened is None else "INCOMPLETE",
            # 0.05 price points adverse per leg per side = $20 extra round-trip.
            "stress_realized_pnl_005_per_leg_per_side": str(total - stress),
            "stress_note": "Post-trade sensitivity only; not a fill or signal replay"}


def replay(archive):
    if archive.get("version") != 1 or archive.get("implementation") != implementation():
        raise ValueError("Archive version/source fingerprint mismatch")
    if archive.get("config") != {"entry_signal": "triple_cross"}:
        from credit_paper import STRATEGIES, validate_risk
        config = archive.get('config', {})
        if not isinstance(config, dict) or set(config) != {'strategy', 'risk', 'fee_per_contract'} or config['strategy'] not in STRATEGIES:
            raise ValueError("Unsupported experiment configuration")
        validate_risk(config['risk'], config['fee_per_contract'])
    state = ndx_paper.initial_state()
    previous = digest({k: v for k, v in archive.items() if k != "records"})
    for sequence, record in enumerate(archive["records"], 1):
        payload = {k: v for k, v in record.items() if k != "hash"}
        if record["sequence"] != sequence or record["previous"] != previous or digest(payload) != record["hash"]:
            raise ValueError("Record sequence/hash mismatch")
        state, event = ndx_paper.step(state, record["snapshot"],
                                     datetime.fromisoformat(record["observed_at"]), **archive["config"])
        if event != record["event"] or digest(state) != record["state_hash"]:
            raise ValueError("Replay output mismatch")
        accounting(state)
        previous = record["hash"]
    return state, accounting(state)


def observe(archive, snapshot, now):
    state, _ = replay(archive)
    new_state, event = ndx_paper.step(state, snapshot, now, **archive["config"])
    accounting(new_state)
    result = deepcopy(archive)
    previous = result["records"][-1]["hash"] if result["records"] else digest(
        {k: v for k, v in result.items() if k != "records"})
    record = {"sequence": len(result["records"]) + 1, "previous": previous,
              "observed_at": now.isoformat(), "snapshot": deepcopy(snapshot),
              "event": event, "state_hash": digest(new_state)}
    record["hash"] = digest(record)
    result["records"].append(record)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--observed-at", help="Explicit timezone-aware observation time")
    parser.add_argument("--init", action="store_true")
    args = parser.parse_args()
    if (os.getenv("TRADING_MODE", "paper").lower() != "paper"
            or os.getenv("ROBINHOOD_LIVE_ORDERS", "false").lower() != "false"
            or os.getenv("ALLOW_0DTE", "false").lower() != "false"):
        parser.error("Paper mode with live orders and 0DTE disabled required")
    if bool(args.snapshot) != bool(args.observed_at):
        parser.error("Snapshot and observation time must be supplied together")
    import fcntl
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with args.archive.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.archive.exists():
            if args.init: parser.error("Archive exists; reset refused")
            archive = json.loads(args.archive.read_text())
        elif args.init:
            archive = new_archive()
        else:
            parser.error("Archive missing; explicit --init required")
        if args.snapshot:
            if archive['config'].get('strategy') in ('iron_condor', 'iron_butterfly'):
                parser.error('Credit observations must use paper_pipeline.py for shared portfolio enforcement; replay here is read-only')
            archive = observe(archive, json.loads(args.snapshot.read_text()), datetime.fromisoformat(args.observed_at))
        _, report = replay(archive)
        if args.snapshot or args.init:
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=args.archive.parent, delete=False) as out:
                    name = out.name
                    json.dump(archive, out, sort_keys=True, allow_nan=False)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(name, args.archive)
            finally:
                if name and os.path.exists(name): os.unlink(name)
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
