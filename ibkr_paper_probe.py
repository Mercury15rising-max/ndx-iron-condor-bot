"""Paper-account handshake and NDX metadata discovery using IBKR's official SDK.

This diagnostic has no order route. Log in to TWS/IB Gateway yourself first.
Chain metadata is not a quote, proof of an open session, or trading readiness.
"""
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import threading


class Unavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class PaperConnection:
    expected_account: str
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 71
    timeout: float = 15.0
    mode: str = "paper"

    def validate(self):
        if self.mode != "paper":
            raise Unavailable("IBKR_MODE must be paper for this integration.")
        if not re.fullmatch(r"DU[0-9]+", self.expected_account):
            raise Unavailable("Set IBKR_EXPECTED_PAPER_ACCOUNT to your DU paper account ID.")
        if self.host != "127.0.0.1":
            raise Unavailable("Run alongside TWS/IB Gateway on 127.0.0.1; remote sockets are not configured.")
        if self.port not in (7497, 4002):
            raise Unavailable("Only default paper ports 7497 (TWS) and 4002 (Gateway) are supported.")
        if isinstance(self.client_id, bool) or not isinstance(self.client_id, int) or self.client_id <= 0:
            raise Unavailable("Use a positive dedicated IBKR_CLIENT_ID, not master client 0.")
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 60:
            raise Unavailable("IBKR_TIMEOUT_SECONDS must be greater than zero and at most 60.")


class ProbeState:
    def __init__(self):
        self.condition = threading.Condition()
        self.failure = None
        self.handshake = False
        self.accounts = None
        self.contracts = []
        self.contracts_done = False
        self.chains = []
        self.chains_done = False
        self.closing = False

    def update(self, **values):
        with self.condition:
            for key, value in values.items():
                setattr(self, key, value)
            self.condition.notify_all()

    def fail(self, reason):
        with self.condition:
            if self.failure is None:
                self.failure = reason
            self.condition.notify_all()

    def wait(self, predicate, timeout, stage):
        with self.condition:
            complete = self.condition.wait_for(lambda: self.failure or predicate(), timeout)
            if self.failure:
                raise Unavailable(self.failure)
            if not complete:
                raise Unavailable("Timed out waiting for " + stage + ".")

    def verify_account(self, expected):
        # A paper port or DU prefix alone is not sufficient. Require exactly the
        # user-configured account and reject mixed live/paper sessions.
        if self.accounts != (expected,):
            raise Unavailable("Connected account does not exactly match the configured paper account.")


def validate_chains(chains, con_id):
    if not chains:
        raise Unavailable("No NDX option-chain metadata was returned.")
    for chain in chains:
        if (chain["underlying_con_id"] != con_id or not chain["exchange"]
                or not chain["trading_class"] or chain["multiplier"] != "100"
                or not chain["expirations"] or not chain["strikes"]):
            raise Unavailable("Incomplete or mismatched NDX option-chain metadata.")
        for expiry in chain["expirations"]:
            if not re.fullmatch(r"[0-9]{8}", expiry):
                raise Unavailable("Malformed option-chain expiration.")
            try:
                datetime.strptime(expiry, "%Y%m%d")
            except ValueError as exc:
                raise Unavailable("Malformed option-chain expiration.") from exc
        if any(isinstance(strike, bool) or not math.isfinite(strike) or strike <= 0
               for strike in chain["strikes"]):
            raise Unavailable("Invalid option-chain strike.")


def make_app(state):
    try:
        from ibapi.client import EClient
        from ibapi.wrapper import EWrapper
        from ibapi.contract import Contract
    except ImportError as exc:
        raise Unavailable("Install IBKR's official TWS API Python SDK on this computer first.") from exc

    class ProbeApp(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)

        def nextValidId(self, orderId):
            state.update(handshake=True)  # Handshake only; no ID is used for an order.

        def managedAccounts(self, accountsList):
            accounts = tuple(x.strip() for x in accountsList.split(",") if x.strip())
            state.update(accounts=accounts)

        def connectionClosed(self):
            if not state.closing:
                state.fail("IBKR disconnected before the diagnostic completed.")

        def error(self, reqId, *args):
            # New SDKs include errorTime before errorCode; older ones do not.
            code = args[1] if len(args) >= 3 and isinstance(args[1], int) else (args[0] if args else None)
            if code not in (2104, 2106, 2107, 2108, 2158):
                # Do not echo broker error strings, account IDs or payloads.
                state.fail("IBKR reported API error code " + str(code) + ".")

        def request_ndx(self):
            contract = Contract()
            contract.symbol = "NDX"
            contract.secType = "IND"
            contract.exchange = "NASDAQ"
            contract.currency = "USD"
            self.reqContractDetails(1001, contract)

        def contractDetails(self, reqId, contractDetails):
            if reqId != 1001:
                return
            c = contractDetails.contract
            with state.condition:
                state.contracts.append({"con_id": c.conId, "symbol": c.symbol,
                                        "security_type": c.secType, "currency": c.currency})

        def contractDetailsEnd(self, reqId):
            if reqId == 1001:
                state.update(contracts_done=True)

        def request_chains(self, con_id):
            self.reqSecDefOptParams(1002, "NDX", "", "IND", con_id)

        def securityDefinitionOptionParameter(self, reqId, exchange, underlyingConId,
                                             tradingClass, multiplier, expirations, strikes):
            if reqId != 1002:
                return
            with state.condition:
                state.chains.append({"exchange": exchange, "underlying_con_id": underlyingConId,
                                     "trading_class": tradingClass, "multiplier": multiplier,
                                     "expirations": sorted(expirations), "strikes": sorted(strikes)})

        def securityDefinitionOptionParameterEnd(self, reqId):
            if reqId == 1002:
                state.update(chains_done=True)

        def deny_orders(self, *args, **kwargs):
            raise Unavailable("Orders are not implemented in the IBKR connection diagnostic.")

        placeOrder = deny_orders
        cancelOrder = deny_orders
        reqGlobalCancel = deny_orders
        exerciseOptions = deny_orders

    return ProbeApp()


def probe(settings, app_factory=make_app):
    report = {"schema_version": 1, "broker": "IBKR", "mode": "paper",
              "status": "UNAVAILABLE", "orders_enabled": False, "trading_ready": False,
              "market_data_verified": False, "planned_risk_limits_usd": {
                  "per_trade": 75, "daily_loss": 75, "total_open_risk": 75}}
    state = ProbeState()
    app = None
    reader = None
    try:
        settings.validate()
        app = app_factory(state)
        app.connect(settings.host, settings.port, clientId=settings.client_id)

        def read():
            try:
                app.run()
            except Exception:
                state.fail("IBKR reader failed; no complete response is available.")

        reader = threading.Thread(target=read, daemon=True)
        reader.start()
        state.wait(lambda: state.handshake and state.accounts is not None,
                   settings.timeout, "handshake and managed accounts")
        state.verify_account(settings.expected_account)
        app.request_ndx()
        state.wait(lambda: state.contracts_done, settings.timeout, "NDX contract details")
        if len(state.contracts) != 1:
            raise Unavailable("NDX underlying discovery returned missing or ambiguous contracts.")
        underlying = state.contracts[0]
        if (underlying["symbol"] != "NDX" or underlying["security_type"] != "IND"
                or underlying["currency"] != "USD" or underlying["con_id"] <= 0):
            raise Unavailable("NDX underlying metadata did not match the requested index.")
        app.request_chains(underlying["con_id"])
        state.wait(lambda: state.chains_done, settings.timeout, "complete option-chain metadata")
        validate_chains(state.chains, underlying["con_id"])
        # Recheck the account: callbacks can change during discovery.
        state.verify_account(settings.expected_account)
        with state.condition:
            if state.failure:
                raise Unavailable(state.failure)
            report.update(status="PAPER_CONNECTION_OK", paper_account_verified=True,
                          underlying=underlying, chains=state.chains)
        report["blockers"] = ["Fresh option quotes, Greeks and session eligibility are not verified.",
                              "Condor/butterfly paper orders and position monitoring are not implemented.",
                              "Fee-inclusive $75 risk and daily-loss enforcement need execution integration."]
    except Unavailable as exc:
        report["blockers"] = [str(exc)]
    except Exception:
        report["blockers"] = ["IBKR diagnostic failed; connection or SDK compatibility needs investigation."]
    finally:
        state.closing = True
        if app is not None:
            try:
                app.disconnect()
            except Exception:
                report.update(status="UNAVAILABLE", trading_ready=False)
                report["blockers"] = ["IBKR disconnect failed; verify local connection cleanup."]
        if reader is not None:
            reader.join(timeout=2)
            if reader.is_alive():
                report.update(status="UNAVAILABLE", trading_ready=False)
                report["blockers"] = ["IBKR reader did not stop after disconnect."]
    # This is an observation timestamp, never a replacement for a market quote timestamp.
    report["observed_at"] = datetime.now(timezone.utc).isoformat()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New report file; existing files are never overwritten.")
    args = parser.parse_args()
    try:
        settings = PaperConnection(
            expected_account=os.getenv("IBKR_EXPECTED_PAPER_ACCOUNT", ""),
            host=os.getenv("IBKR_HOST", "127.0.0.1"), port=int(os.getenv("IBKR_PORT", "7497")),
            client_id=int(os.getenv("IBKR_CLIENT_ID", "71")),
            timeout=float(os.getenv("IBKR_TIMEOUT_SECONDS", "15")), mode=os.getenv("IBKR_MODE", "paper"))
    except ValueError:
        parser.exit(2, "IBKR port, client ID and timeout must be numeric.\n")
    if args.output and args.output.exists():
        parser.exit(2, "Output already exists; choose a new filename.\n")
    report = probe(settings)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
    print(text, end="")
    return 0 if report["status"] == "PAPER_CONNECTION_OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
