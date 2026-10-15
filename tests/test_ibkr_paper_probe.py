"""Offline fixtures only; never connect to IBKR or submit any orders."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from ibkr_paper_probe import PaperConnection, Unavailable, make_app, probe


ACCOUNT = "DU1234567"  # Synthetic account, not a user's credential.
UNDERLYING = {"con_id": 123, "symbol": "NDX", "security_type": "IND", "currency": "USD"}
CHAIN = {"underlying_con_id": 123, "exchange": "SMART", "trading_class": "NDXP",
         "multiplier": "100", "expirations": ["20261016"], "strikes": [25000.0, 25005.0]}


class FakeApp:
    def __init__(self, state):
        self.state = state
        self.requests = []
        self.stopped = False

    def connect(self, host, port, clientId):
        self.state.update(handshake=True, accounts=(ACCOUNT,))

    def run(self):
        pass

    def request_ndx(self):
        self.requests.append("underlying")
        self.state.update(contracts=[copy.deepcopy(UNDERLYING)], contracts_done=True)

    def request_chains(self, con_id):
        self.requests.append("chains")
        self.state.update(chains=[copy.deepcopy(CHAIN)], chains_done=True)

    def disconnect(self):
        self.stopped = True


class PaperProbeTests(unittest.TestCase):
    def run_probe(self, cls=FakeApp, **settings):
        apps = []

        def factory(state):
            app = cls(state)
            apps.append(app)
            return app

        result = probe(PaperConnection(ACCOUNT, timeout=0.01, **settings), factory)
        return result, apps

    def test_complete_connection_is_not_trading_readiness(self):
        report, apps = self.run_probe()
        self.assertEqual(report["status"], "PAPER_CONNECTION_OK")
        self.assertFalse(report["orders_enabled"])
        self.assertFalse(report["trading_ready"])
        self.assertFalse(report["market_data_verified"])
        self.assertNotIn(ACCOUNT, json.dumps(report))
        self.assertEqual(report["chains"][0]["expirations"], ["20261016"])
        self.assertNotIn("quote_timestamp", report)
        self.assertTrue(apps[0].stopped)

    def test_invalid_settings_do_not_connect(self):
        for settings in ({"mode": "live"}, {"port": 7496}, {"port": 4001},
                         {"host": "example.com"}, {"client_id": 0}):
            with self.subTest(settings=settings):
                result, apps = self.run_probe(**settings)
                self.assertEqual(result["status"], "UNAVAILABLE")
                self.assertEqual(apps, [])
        with self.assertRaises(Unavailable):
            PaperConnection("U1234567").validate()
        with self.assertRaises(Unavailable):
            PaperConnection(ACCOUNT, timeout=float("nan")).validate()

    def test_both_paper_ports_validate(self):
        for port in (7497, 4002):
            PaperConnection(ACCOUNT, port=port).validate()

    def test_wrong_or_mixed_accounts_rejected_before_requests(self):
        for accounts in (("U1234567",), ("DU9999999",), (ACCOUNT, "U1234567"), ()):
            class WrongAccount(FakeApp):
                def connect(self, *args, **kwargs):
                    self.state.update(handshake=True, accounts=accounts)
            result, apps = self.run_probe(WrongAccount)
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertEqual(apps[0].requests, [])
            self.assertTrue(apps[0].stopped)

    def test_handshake_and_timeout_required(self):
        class MissingHandshake(FakeApp):
            def connect(self, *args, **kwargs):
                self.state.update(accounts=(ACCOUNT,))
        result, apps = self.run_probe(MissingHandshake)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertIn("Timed out", result["blockers"][0])
        self.assertEqual(apps[0].requests, [])

    def test_ambiguous_underlying_rejected(self):
        class Ambiguous(FakeApp):
            def request_ndx(self):
                self.state.update(contracts=[UNDERLYING, UNDERLYING], contracts_done=True)
        result, apps = self.run_probe(Ambiguous)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertNotIn("chains", apps[0].requests)

    def test_mismatched_underlying_rejected(self):
        class WrongUnderlying(FakeApp):
            def request_ndx(self):
                self.state.update(contracts=[dict(UNDERLYING, symbol="SPX")], contracts_done=True)
        result, apps = self.run_probe(WrongUnderlying)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertNotIn("chains", apps[0].requests)

    def test_invalid_chains_rejected(self):
        for change in ({"underlying_con_id": 999}, {"multiplier": "10"}, {"expirations": []},
                       {"expirations": ["20260230"]}, {"strikes": [float("nan")]},
                       {"strikes": [-1]}, {"trading_class": ""}):
            class BadChain(FakeApp):
                def request_chains(self, con_id):
                    self.state.update(chains=[dict(CHAIN, **change)], chains_done=True)
            result, _ = self.run_probe(BadChain)
            self.assertEqual(result["status"], "UNAVAILABLE")

    def test_partial_chain_response_does_not_pass(self):
        class Partial(FakeApp):
            def request_chains(self, con_id):
                self.state.update(chains=[CHAIN])
        result, apps = self.run_probe(Partial)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertTrue(apps[0].stopped)

    def test_account_change_during_discovery_rejected(self):
        class ChangedAccount(FakeApp):
            def request_chains(self, con_id):
                super().request_chains(con_id)
                self.state.update(accounts=("U1234567",))
        result, _ = self.run_probe(ChangedAccount)
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_reader_failure_cleans_up(self):
        class FailedReader(FakeApp):
            def run(self):
                raise RuntimeError("Private broker error must not escape")
        result, apps = self.run_probe(FailedReader)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertNotIn("Private broker", json.dumps(result))
        self.assertTrue(apps[0].stopped)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "report.json"
            p.write_text("existing archive")
            env = dict(os.environ, IBKR_EXPECTED_PAPER_ACCOUNT=ACCOUNT)
            result = subprocess.run([sys.executable, "ibkr_paper_probe.py", "--output", str(p)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(p.read_text(), "existing archive")


class SDKCallbackTests(unittest.TestCase):
    def app(self):
        from ibkr_paper_probe import ProbeState
        class Client:
            def __init__(self, wrapper):
                self.calls = []
            def reqContractDetails(self, *args):
                self.calls.append(("underlying", args))
            def reqSecDefOptParams(self, *args):
                self.calls.append(("chains", args))
        modules = {name: ModuleType(name) for name in
                   ("ibapi", "ibapi.client", "ibapi.wrapper", "ibapi.contract")}
        modules["ibapi.client"].EClient = Client
        modules["ibapi.wrapper"].EWrapper = type("Wrapper", (), {})
        modules["ibapi.contract"].Contract = type("Contract", (), {})
        state = ProbeState()
        with patch.dict(sys.modules, modules):
            app = make_app(state)
        return app, state

    def test_official_request_shapes_and_callbacks(self):
        app, state = self.app()
        app.nextValidId(99)
        app.managedAccounts(ACCOUNT + ",")
        app.request_ndx()
        contract = app.calls[0][1][1]
        self.assertEqual((contract.symbol, contract.secType, contract.exchange), ("NDX", "IND", "NASDAQ"))
        app.contractDetails(1001, SimpleNamespace(contract=SimpleNamespace(
            conId=123, symbol="NDX", secType="IND", currency="USD")))
        app.contractDetailsEnd(1001)
        app.request_chains(123)
        self.assertEqual(app.calls[-1], ("chains", (1002, "NDX", "", "IND", 123)))
        app.securityDefinitionOptionParameter(1002, "SMART", 123, "NDXP", "100", {"20261016"}, {25000.0})
        app.securityDefinitionOptionParameterEnd(1002)
        self.assertTrue(state.handshake and state.contracts_done and state.chains_done)
        self.assertEqual(state.accounts, (ACCOUNT,))

    def test_old_and_new_sdk_error_signatures(self):
        for args in ((502, "sensitive error"), (1760000000, 502, "sensitive error", "")):
            app, state = self.app()
            app.error(-1, *args)
            self.assertIn("502", state.failure)
            self.assertNotIn("sensitive", state.failure)

    def test_order_methods_are_not_available(self):
        app, _ = self.app()
        for name in ("placeOrder", "cancelOrder", "reqGlobalCancel", "exerciseOptions"):
            with self.assertRaises(Unavailable):
                getattr(app, name)(1, object())

    def test_disconnect_and_informational_messages(self):
        app, state = self.app()
        app.error(-1, 2104, "Market data farm connected")
        self.assertIsNone(state.failure)
        app.connectionClosed()
        self.assertIsNotNone(state.failure)
