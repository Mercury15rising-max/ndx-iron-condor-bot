"""Deterministic NDXP paper-only engine; consumes snapshots, never brokerage orders."""
import argparse
from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo
from ema_signals import evaluate_ema
from exchange_session import session_at

CT = ZoneInfo("America/New_York")
D = Decimal


def number(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite number")
    return result


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include timezone")
    return result


def fresh(value, now):
    try:
        return 0 <= (now - timestamp(value)).total_seconds() <= 60
    except (ValueError, TypeError, AttributeError):
        return False


def initial_state():
    return {"version": 1, "engine": "ndxp_v1", "balance": "3000", "position": None,
            "completed": 0, "daily_pnl": {}, "events": [], "last_observed": None}


def usable_quote(q, now):
    try:
        return (fresh(q["updated_at"], now)
                and 0 < number(q["bid_price"]) <= number(q["ask_price"])
                and number(q["bid_size"]) >= 1 and number(q["ask_size"]) >= 1)
    except (KeyError, ValueError, TypeError, InvalidOperation):
        return False


def regular_session(now):
    verified = session_at(now)
    return verified["date"] if verified else None


def step(state, snapshot, now, *, entry_signal="triple_cross", strategy="call_debit_spread", risk=None, fee_per_contract="0.50"):
    """Return new state + event. Caller must persist them together atomically.

    snapshot: chains/instruments arrays, quotes array of quote objects (not wrappers),
    complete=true for entry selection, session_open=true and session_observed_at
    from a verified exchange-calendar/data source. No inferred holiday openings.
    """
    if strategy != "call_debit_spread":
        from credit_paper import step as credit_step
        return credit_step(state, snapshot, now, strategy=strategy, risk=risk, fee_per_contract=fee_per_contract)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if entry_signal != "triple_cross":
        raise ValueError("Unknown entry signal")
    if state.get("version") != 1 or state.get("engine") != "ndxp_v1":
        raise ValueError("Unsupported paper state")
    if state["last_observed"] and now <= timestamp(state["last_observed"]):
        raise ValueError("Observation must advance; replay rejected")
    state = deepcopy(state)
    number(state["balance"])
    state["last_observed"] = now.isoformat()

    def finish(action, reason, **details):
        event = {"at": now.isoformat(), "action": action, "reason": reason,
                 "paper_only": True, **details}
        state["events"].append(event)
        return state, event

    session = regular_session(now)
    if (session is None or snapshot.get("session_open") is not True
            or not fresh(snapshot.get("session_observed_at"), now)):
        return finish("UNRESOLVED" if state["position"] else "UNAVAILABLE",
                      "Verified open regular session required")

    rows = snapshot.get("quotes", [])
    if not isinstance(rows, list) or any(not isinstance(q, dict) for q in rows):
        return finish("UNAVAILABLE", "Malformed quote list")
    if any(not isinstance(q.get("instrument_id"), str) or not q["instrument_id"] for q in rows):
        return finish("UNRESOLVED" if state["position"] else "UNAVAILABLE", "Missing or malformed quote IDs")
    quotes = {q["instrument_id"]: q for q in rows}
    if None in quotes or len(quotes) != len(rows):
        return finish("UNAVAILABLE", "Missing or duplicate quote IDs")

    position = state["position"]
    if position:
        long = quotes.get(position["long"]["id"], {})
        short = quotes.get(position["short"]["id"], {})
        if not all(usable_quote(q, now) for q in (long, short)):
            return finish("UNRESOLVED", "Missing/stale/invalid exit quotes; entry blocked")
        # A repeated, pre-entry book is not a new executable observation.
        if any(timestamp(q["updated_at"]) <= timestamp(position["opened_at"])
               for q in (long, short)):
            return finish("UNRESOLVED", "Exit requires quotes newer than paper entry")
        entry = number(position["entry_cost"])
        value = (number(long["bid_price"]) - number(short["ask_price"])) * 100 - 2
        pnl = value - entry
        threshold = -D("0.30") * entry
        age = (now - timestamp(position["opened_at"])).total_seconds()
        action = "STOP_LOSS" if pnl <= threshold else "TIME_EXIT" if age >= 3600 else "HOLD"
        details = {"entry_cost": str(entry), "exit_value": str(value),
                   "net_pnl": str(pnl), "stop_threshold": str(threshold),
                   "loss_beyond_threshold": str(max(D(0), threshold - pnl)),
                   "position": position, "long_quote": long, "short_quote": short}
        if action != "HOLD":
            state["balance"] = str(number(state["balance"]) + value)
            state["daily_pnl"][session] = str(number(state["daily_pnl"].get(session, 0)) + pnl)
            state["position"] = None
            state["completed"] += 1
        return finish(action, "Observed bid/ask valuation, including $2 modeled exit fees", **details)

    local = now.astimezone(CT)
    if not time(10) <= local.time() < time(14, 30):
        return finish("NO_TRADE", "Entry window is 10:00-14:30 New York")
    if any(e.get("action") == "PAPER_ENTRY" and timestamp(e["at"]).astimezone(CT).date() == local.date()
           for e in state["events"]):
        return finish("NO_TRADE", "One paper entry per day")
    if snapshot.get("signal_symbol") != "QQQ":
        return finish("NO_TRADE", "Explicit QQQ proxy candles required")
    if state["completed"] >= 30:
        return finish("COMPLETE", "30 paper trades completed; review required")
    if number(state["daily_pnl"].get(session, 0)) <= -300:
        return finish("NO_TRADE", "Session realized-loss limit reached")
    if snapshot.get("complete") is not True:
        return finish("NO_TRADE", "Complete contract/quote snapshot required for selection")

    signal = None
    if entry_signal != "baseline":
        signal = evaluate_ema(snapshot.get("signal_bars", []), now,
                              symbol=snapshot.get("signal_symbol"), timeframe_seconds=300,
                              regular_sessions=True)
        if not signal["ready"] or signal[entry_signal] != "bullish":
            return finish("NO_TRADE", "Fresh bullish entry signal required", signal=signal)
        key = signal["symbol"] + ":" + signal["bar_close"]
        if state.get("last_signal_bar") == key:
            return finish("NO_TRADE", "Crossover bar already used", signal=signal)

    chain_rows = snapshot.get("chains", [])
    instruments = snapshot.get("instruments", [])
    if (not isinstance(chain_rows, list) or not isinstance(instruments, list)
            or any(not isinstance(c, dict) or not isinstance(c.get("id"), str) or not c["id"] for c in chain_rows)
            or any(not isinstance(i, dict) or not isinstance(i.get("id"), str) or not i["id"] for i in instruments)
            or len({c["id"] for c in chain_rows}) != len(chain_rows)):
        return finish("NO_TRADE", "Malformed contract metadata")
    chains = {c["id"] for c in chain_rows
              if c.get("symbol") == "NDXP" and c.get("settle_on_open") is False
              and c.get("can_open_position") is True
              and str(c.get("trade_value_multiplier")) in ("100", "100.0000")}
    ids = [i.get("id") for i in instruments]
    if None in ids or len(set(ids)) != len(ids):
        return finish("NO_TRADE", "Missing or duplicate instrument IDs")
    eligible = []
    for i in instruments:
        try:
            expiry = date.fromisoformat(i["expiration_date"])
            days = (expiry - now.astimezone(CT).date()).days
            if (i["chain_id"] in chains and i["chain_symbol"] == "NDXP"
                    and i["type"] == "call" and i["state"] == "active"
                    and i["tradability"] == "tradable" and 1 <= days <= 3
                    and number(i["trade_value_multiplier"]) == 100
                    and number(i["strike_price"]) > 0):
                eligible.append(i)
        except (KeyError, ValueError, TypeError, InvalidOperation):
            return finish("NO_TRADE", "Malformed instrument metadata")
    if not eligible:
        return finish("NO_TRADE", "No eligible PM-settled NDXP calls")
    # Earliest eligible expiry, then nearest delta; ties favor lower strike and ID.
    expiry = min(i["expiration_date"] for i in eligible)
    eligible = [i for i in eligible if i["expiration_date"] == expiry]
    ranked = []
    for i in eligible:
        q = quotes.get(i["id"], {})
        if not usable_quote(q, now):
            continue
        try:
            delta = number(q["delta"])
            if not 0 <= delta <= 1:
                raise ValueError("Invalid call delta")
            ranked.append((abs(delta - D("0.30")), number(i["strike_price"]), i["id"], i))
        except (KeyError, ValueError, TypeError, InvalidOperation):
            continue
    if not ranked:
        return finish("NO_TRADE", "No fresh eligible calls with valid deltas")
    long_i = min(ranked, key=lambda r: r[:3])[3]
    shorts = [i for i in eligible if i["chain_id"] == long_i["chain_id"]
              and number(i["strike_price"]) == number(long_i["strike_price"]) + 5]
    if len(shorts) != 1:
        return finish("NO_TRADE", "Unique 5-point protective short leg unavailable")
    short_i = shorts[0]
    long, short = quotes[long_i["id"]], quotes.get(short_i["id"], {})
    if not usable_quote(short, now):
        return finish("NO_TRADE", "Protective short leg quote is not usable")
    debit = (number(long["ask_price"]) - number(short["bid_price"])) * 100
    entry = debit + 2
    if debit <= 0 or entry > min(D(150), number(state["balance"])):
        return finish("NO_TRADE", "Selected spread violates positive-debit/cost limit",
                      calculated_cost=str(entry), long=long_i, short=short_i)
    state["position"] = {"long": long_i, "short": short_i, "opened_at": now.isoformat(),
                         "entry_cost": str(entry), "long_quote": long, "short_quote": short,
                         "entry_signal": entry_signal, "signal": signal}
    if signal:
        state["last_signal_bar"] = signal["symbol"] + ":" + signal["bar_close"]
    state["balance"] = str(number(state["balance"]) - entry)
    return finish("PAPER_ENTRY", "Hypothetical quote-based fill; $2 modeled entry fees",
                  position=state["position"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--state", type=Path, default=Path("data/ndx_paper_state.json"))
    parser.add_argument("--init", action="store_true", help="Explicitly create a new paper ledger")
    parser.add_argument("--entry-signal", choices=("triple_cross",),
                        default="triple_cross", help="Opt-in completed 5-minute EMA entry filter")
    args = parser.parse_args()
    if os.getenv("TRADING_MODE", "paper").lower() != "paper" or os.getenv(
            "ROBINHOOD_LIVE_ORDERS", "false").lower() != "false":
        parser.error("This engine requires paper mode and live orders disabled")
    import fcntl  # Linux/macOS single-writer protection; no network client in this module.
    args.state.parent.mkdir(parents=True, exist_ok=True)
    with args.state.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.state.exists():
            if args.init:
                parser.error("Ledger already exists; refusing to reset it")
            state = json.loads(args.state.read_text())
        elif args.init:
            state = initial_state()
        else:
            parser.error("Missing ledger; use --init only for a genuinely new paper test")
        state, event = step(state, json.loads(args.snapshot.read_text()), datetime.now(timezone.utc),
                            entry_signal=args.entry_signal)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=args.state.parent, delete=False) as out:
                name = out.name
                json.dump(state, out, indent=2, allow_nan=False)
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, args.state)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)
        print(json.dumps(event, indent=2))


if __name__ == "__main__":
    main()
