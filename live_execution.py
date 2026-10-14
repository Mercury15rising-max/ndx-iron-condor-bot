"""Explicitly reviewed live iron-condor execution through an injected MCP client.

This module does not start a scheduler or infer the user's net limit price.
"""
import json
import sqlite3
import time
from decimal import Decimal
from uuid import UUID, uuid4

from models import IronCondor


def unwrap(result):
    """Accept decoded connector results or SDK CallToolResult objects."""
    if isinstance(result, dict):
        if result.get("isError"):
            raise RuntimeError("Robinhood MCP returned an error.")
        body = result.get("structuredContent", result)
    else:
        if result.isError:
            raise RuntimeError("Robinhood MCP returned an error.")
        body = result.structuredContent
        if body is None:
            blocks = [block.text for block in result.content if block.type == "text"]
            if len(blocks) != 1:
                raise RuntimeError("Unrecognized Robinhood MCP response.")
            body = json.loads(blocks[0])
    if not isinstance(body, dict) or not isinstance(body.get("data"), dict):
        raise RuntimeError("Missing Robinhood response data.")
    return body["data"]


def build_live_payload(condor: IronCondor, *, account_number, instruments,
                       limit_price, quantity=1, max_risk=500):
    if not isinstance(account_number, str) or not account_number.strip():
        raise ValueError("An explicit account number is required.")
    if type(quantity) is not int or quantity < 1:
        raise ValueError("Quantity must be a positive integer.")
    price = Decimal(str(limit_price))
    risk_limit = Decimal(str(max_risk))
    if not price.is_finite() or price <= 0 or not risk_limit.is_finite() or risk_limit <= 0:
        raise ValueError("Price and risk limit must be finite and positive.")
    options = (condor.long_put, condor.short_put, condor.short_call, condor.long_call)
    strikes = [Decimal(str(option.strike)) for option in options]
    if not all(strike.is_finite() for strike in strikes) or not all(
        a < b for a, b in zip(strikes, strikes[1:])
    ):
        raise ValueError("Invalid iron-condor strike order.")
    if [option.option_type for option in options] != ["put", "put", "call", "call"]:
        raise ValueError("Invalid iron-condor option types.")
    if any(option.symbol != options[0].symbol or option.expiration != condor.expiration
           for option in options):
        raise ValueError("All legs must share the same chain and expiration.")
    width = max(strikes[1] - strikes[0], strikes[3] - strikes[2])
    # Recompute loss at the supplied price; never trust a stored model risk value.
    if price >= width or (width - price) * 100 * quantity > risk_limit:
        raise ValueError("Order exceeds risk limit or has an invalid credit.")
    legs = []
    for option, side in zip(options, ("buy", "sell", "sell", "buy")):
        matches = [row for row in instruments if row and
                   row.get("chain_symbol") == option.symbol and
                   row.get("expiration_date") == option.expiration.isoformat() and
                   row.get("type") == option.option_type and
                   Decimal(str(row.get("strike_price"))) == Decimal(str(option.strike))]
        if len(matches) != 1:
            raise ValueError("Each leg must resolve to exactly one verified contract.")
        row = matches[0]
        if (row.get("state") != "active" or row.get("tradability") != "tradable" or
                row.get("underlying_type") != "index" or
                Decimal(str(row.get("trade_value_multiplier"))) != 100):
            raise ValueError("Contract is not an active standard index option.")
        option_id = str(UUID(row["id"]))
        legs.append(dict(option_id=option_id, side=side, position_effect="open", ratio_quantity=1))
    if len({leg["option_id"] for leg in legs}) != 4:
        raise ValueError("Duplicate option contracts.")
    return dict(account_number=account_number, legs=legs, direction="credit",
                quantity=str(quantity), price=str(price), type="limit",
                time_in_force="gfd", market_hours="regular_hours")


class LiveOptionExecutor:
    """One-time review tickets with durable submission-attempt tracking.

    The caller must run portfolio, quote, event and market-session gates before
    review and submission. Review alerts and the complete payload must be shown
    to the user, who must approve that exact ticket before submit is called.
    """

    def __init__(self, client, *, journal_path, entry_gate, enabled=False, clock=time.time):
        self.client, self.enabled, self.clock = client, enabled, clock
        self.entry_gate = entry_gate
        self.db = sqlite3.connect(journal_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS orders "
                        "(ref_id TEXT PRIMARY KEY, payload TEXT NOT NULL, reviewed REAL NOT NULL, "
                        "state TEXT NOT NULL, response TEXT)")
        self.db.commit()

    def close(self):
        self.db.close()

    async def _eligible(self, account_number):
        data = unwrap(await self.client.call_tool("get_accounts", {}))
        accounts = [a for a in data.get("accounts", []) or [] if a and
                    a.get("account_number") == account_number]
        if len(accounts) != 1:
            raise RuntimeError("Selected account is unavailable.")
        account = accounts[0]
        if (account.get("agentic_allowed") is not True or
                account.get("user_option_level", account.get("option_level")) != "option_level_3" or
                account.get("brokerage_account_type") != "individual" or
                account.get("type") not in {"margin", "limited_margin"} or
                account.get("state") != "active" or
                account.get("deactivated") is not False or
                account.get("permanently_deactivated") is not False):
            raise RuntimeError("Selected account is not eligible for live spreads.")

    async def review(self, condor, *, account_number, limit_price, quantity=1, max_risk=500):
        if not self.enabled:
            raise RuntimeError("Live execution is disabled.")
        if await self.entry_gate() is not True:
            raise RuntimeError("Live entry gate rejected this order.")
        await self._eligible(account_number)
        args = dict(chain_symbol=condor.short_put.symbol,
                    expiration_dates=condor.expiration.isoformat(), state="active", tradability="tradable")
        instruments = []
        while True:
            data = unwrap(await self.client.call_tool("get_option_instruments", args))
            instruments.extend(data.get("instruments", []) or [])
            cursor = data.get("next")
            if not cursor:
                break
            if cursor == args.get("cursor"):
                raise RuntimeError("Repeated contract pagination cursor.")
            args["cursor"] = cursor
        payload = build_live_payload(condor, account_number=account_number,
                                     instruments=instruments, limit_price=limit_price,
                                     quantity=quantity, max_risk=max_risk)
        review_args = dict(payload, chain_symbol=condor.short_put.symbol, underlying_type="index")
        result = unwrap(await self.client.call_tool("review_option_order", review_args))
        # Keep the full broker result so alerts can be shown verbatim to the user.
        ticket = str(uuid4())
        self.db.execute("INSERT INTO orders VALUES (?, ?, ?, 'reviewed', ?)",
                        (ticket, json.dumps(payload, sort_keys=True), self.clock(), json.dumps(result)))
        self.db.commit()
        return dict(ref_id=ticket, payload=payload, review=result)

    async def submit(self, ref_id, *, confirmed=False):
        if not self.enabled or confirmed is not True:
            raise RuntimeError("Live execution and explicit approval of this review are required.")
        row = self.db.execute("SELECT payload, reviewed, state FROM orders WHERE ref_id=?",
                              (ref_id,)).fetchone()
        if row is None or row[2] != "reviewed":
            raise RuntimeError("Review is missing or submission was already attempted; reconcile with broker.")
        age = self.clock() - row[1]
        if not 0 <= age <= 30:
            raise RuntimeError("Review expired; obtain a fresh review and approval.")
        payload = json.loads(row[0])
        if await self.entry_gate() is not True:
            raise RuntimeError("Live entry gate rejected this order.")
        await self._eligible(payload["account_number"])
        if not 0 <= self.clock() - row[1] <= 30:
            raise RuntimeError("Review expired during eligibility checks.")
        # Atomic claim before network I/O prevents duplicate placement on restart
        # or concurrent calls. Ambiguous failures require broker reconciliation.
        cursor = self.db.execute("UPDATE orders SET state='attempted' WHERE ref_id=? AND state='reviewed'",
                                 (ref_id,))
        self.db.commit()
        if cursor.rowcount != 1:
            raise RuntimeError("Submission already attempted.")
        result = unwrap(await self.client.call_tool("place_option_order", dict(payload, ref_id=ref_id)))
        self.db.execute("UPDATE orders SET state='responded', response=? WHERE ref_id=?",
                        (json.dumps(result), ref_id))
        self.db.commit()
        # A response is not a fill; the caller must reconcile order status.
        return result
