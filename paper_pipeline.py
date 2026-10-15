"""Validate exported read-only data and persist NDXP paper observations.

No network client or order tools. Missing data is never replaced with fixtures.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import InvalidOperation
import json
import os
from pathlib import Path
import tempfile

from exchange_session import NY, bounds, session_at, validate_closes
from ndx_paper import number, timestamp, usable_quote
from paper_replay import new_archive, observe, replay


def validate_history(bundle, now):
    bars = bundle.get("candles")
    if not isinstance(bars, list) or not bars:
        raise ValueError("Actual five-minute QQQ candles required")
    ends = []
    per_day = {}
    for bar in bars:
        if not isinstance(bar, dict):
            raise ValueError("Malformed candle")
        if not isinstance(bar.get("close_time"), str):
            raise ValueError("Candle close_time must be a timezone-aware ISO string")
        end = timestamp(bar["close_time"])
        if (bar.get("symbol") != "QQQ" or bar.get("timeframe_seconds") != 300
                or bar.get("closed") is not True or bar.get("interpolated") is True
                or end > now):
            raise ValueError("Only completed, non-interpolated QQQ five-minute candles accepted")
        o, h, low, c, v = (number(bar[k]) for k in ("open", "high", "low", "close", "volume"))
        if not 0 < low <= min(o, c) <= max(o, c) <= h or v < 0:
            raise ValueError("Invalid candle OHLC/volume")
        ends.append(end)
        per_day.setdefault(end.astimezone(NY).date(), []).append(end)
    validate_closes(ends)
    completed = []
    for day, closes in per_day.items():
        start, end = bounds(day)
        if end <= now:
            expected = int((end-start).total_seconds() // 300)
            if len(closes) != expected or closes[0] != start + timedelta(minutes=5) or closes[-1] != end:
                raise ValueError("Completed session has incomplete five-minute history")
            completed.append(day.isoformat())
    if len(completed) < 3:
        raise ValueError("At least three complete trading sessions required")
    if not 0 <= (now-ends[-1]).total_seconds() <= 300:
        raise ValueError("Latest completed candle is stale")
    return bars, completed


def build_snapshot(bundle, now, *, allow_fixtures=False, exit_only=False):
    if bundle.get("version") != 1:
        raise ValueError("Unsupported data bundle")
    source = bundle.get("source")
    if not isinstance(source, dict) or not source.get("name"):
        raise ValueError("Named data source required")
    if source.get("kind") not in ("observed", "fixture"):
        raise ValueError("Explicit observed/fixture provenance required")
    if source["kind"] == "fixture" and not allow_fixtures:
        raise ValueError("Synthetic fixture data requires explicit --allow-fixtures")
    if timestamp(bundle["observed_at"]) != now:
        raise ValueError("Bundle observation timestamp mismatch")
    history_error = None
    try:
        bars, completed = validate_history(bundle, now)
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        if not exit_only:
            raise
        bars, completed = [], []
        history_error = str(error)
    # All option fields and extra provider metadata survive unchanged.
    option_data = deepcopy(bundle.get("options", {}))
    if not isinstance(option_data, dict):
        raise ValueError("Malformed options export")
    for name in ("chains", "instruments", "quotes"):
        # Exits use persisted contracts. Preserve incoming entry metadata for
        # audit, but do not let its availability prevent quote-based exits.
        if exit_only and name in ("chains", "instruments"):
            continue
        rows = option_data.get(name, [])
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"Malformed {name}")
        key = "instrument_id" if name == "quotes" else "id"
        ids = [row.get(key) for row in rows]
        if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f"Missing/duplicate {name} IDs")
    for quote in option_data.get("quotes", []):
        if not exit_only and not usable_quote(quote, now):
            raise ValueError("Stale/missing/crossed option bid/ask, size, or timestamp")
    verified = session_at(now)
    return {**option_data, "complete": option_data.get("complete") is True,
            "signal_symbol": "QQQ", "signal_bars": deepcopy(bars),
            "session_open": verified is not None, "session_observed_at": now.isoformat(),
            "calendar": verified,
            "provenance": {"source": deepcopy(source), "completed_sessions": completed,
                           "candle_count": len(bars), "observed_at": bundle["observed_at"],
                           "history_unavailable": history_error}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--strategy", choices=("call_debit_spread", "iron_condor", "iron_butterfly"),
                        help="New archive strategy; existing archives retain their strategy")
    parser.add_argument("--fee-per-contract", help="Credit strategy modeled fee per leg per side; default 0.50")
    parser.add_argument("--portfolio", type=Path, help="Shared fixture database override; observed runs use the fixed bot portfolio")
    parser.add_argument("--selection-plan", type=Path, help="Frozen explicit contract plan required for new observed credit experiments")
    parser.add_argument("--selection-rules", choices=('fixed_ndxp_condor_v1',), help="Fixed first-experiment condor rules; no butterfly fallback")
    parser.add_argument("--historical", action="store_true", help="Explicit offline replay, not forward fills")
    parser.add_argument("--allow-fixtures", action="store_true", help="Synthetic regression validation only")
    args = parser.parse_args()
    if (os.getenv("TRADING_MODE", "paper").lower() != "paper"
            or os.getenv("ROBINHOOD_LIVE_ORDERS", "false").lower() != "false"
            or os.getenv("ALLOW_0DTE", "false").lower() != "false"):
        parser.error("Paper mode with live orders and 0DTE disabled required")
    bundle = json.loads(args.bundle.read_text())
    now = timestamp(bundle["observed_at"])
    if not args.historical and not 0 <= (datetime.now(timezone.utc)-now).total_seconds() <= 60:
        parser.error("Forward bundle must be observed within 60 seconds; use --historical for offline replay")
    if args.allow_fixtures and not args.historical:
        parser.error("Fixtures are only allowed in explicitly historical regression runs")
    from paper_portfolio import OBSERVED_PORTFOLIO, apply_observation, locked_portfolio, reconcile_exports, archive_lock_path
    fixture = bundle.get('source', {}).get('kind') == 'fixture'
    portfolio_path = args.portfolio or (args.archive.parent / 'fixture-portfolio.sqlite3' if fixture else OBSERVED_PORTFOLIO)
    if not fixture and portfolio_path.resolve() != OBSERVED_PORTFOLIO.resolve():
        parser.error('Observed credit runs cannot select an independent portfolio')
    archive_lock=archive_lock_path(args.archive)
    if archive_lock == portfolio_path.resolve().with_suffix('.lock'):
        parser.error('Archive lock must not overlap the portfolio lock')
    if portfolio_path.exists():
        with locked_portfolio(portfolio_path) as db:
            reconcile_exports(db)  # recover committed observations before reading JSON
    import fcntl
    args.archive.parent.mkdir(parents=True, exist_ok=True)
    with archive_lock.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.archive.exists():
            if args.init:
                parser.error("Archive exists; refusing reset")
            archive = json.loads(args.archive.read_text())
        elif args.init:
            rules=args.selection_rules
            if not fixture and args.strategy=='iron_condor':
                rules=rules or 'fixed_ndxp_condor_v1'
            archive = new_archive(args.strategy or "call_debit_spread", args.fee_per_contract or "0.50", rules)
        else:
            parser.error("Archive missing; explicit --init required")
        current_state, _ = replay(archive)
        saved_strategy = archive['config'].get('strategy', 'call_debit_spread')
        if args.selection_rules and args.selection_rules != archive['config'].get('selection_rules'):
            parser.error('Cannot change selection rules of an existing archive')
        if args.strategy and args.strategy != saved_strategy:
            parser.error('Cannot change the strategy of an existing archive')
        if args.fee_per_contract and (saved_strategy == 'call_debit_spread' or number(args.fee_per_contract) != number(archive['config']['fee_per_contract'])):
            parser.error('Cannot change fees of an existing archive or debit strategy')
        snapshot = build_snapshot(bundle, now, allow_fixtures=args.allow_fixtures,
                                  exit_only=current_state["position"] is not None)
        snapshot["provenance"]["run_mode"] = "historical" if args.historical else "forward"
        prior_sources = [r["snapshot"].get("provenance", {}).get("source") for r in archive["records"]]
        if any(s != snapshot["provenance"]["source"] for s in prior_sources):
            parser.error("Do not mix fixture/observed sources or experiment provenance")
        if saved_strategy in ('iron_condor', 'iron_butterfly'):
            plan = json.loads(args.selection_plan.read_text()) if args.selection_plan else None
            archive, state, report = apply_observation(portfolio_path, args.archive, archive, snapshot, now,
                                                       initializing=args.init, plan=plan)
            print(json.dumps({"action": state["events"][-1]["action"], "report": report,
                              "provenance": snapshot["provenance"]}, indent=2))
            return
        archive = observe(archive, snapshot, now)
        state, report = replay(archive)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=args.archive.parent, delete=False) as out:
                name = out.name
                json.dump(archive, out, sort_keys=True, allow_nan=False)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, args.archive)
            directory = os.open(args.archive.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        print(json.dumps({"action": state["events"][-1]["action"], "report": report,
                          "provenance": snapshot["provenance"]}, indent=2))


if __name__ == "__main__":
    main()
