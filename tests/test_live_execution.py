import tempfile
import unittest
from datetime import date
from dataclasses import replace
from uuid import uuid4

from live_execution import LiveOptionExecutor, build_live_payload, unwrap
from models import IronCondor, OptionQuote


def fixture():
    expiry = date(2026, 10, 16)
    options = [OptionQuote("NDXP", expiry, strike, kind, 1, 2, 0.12)
               for strike, kind in [(100, "put"), (105, "put"), (115, "call"), (120, "call")]]
    condor = IronCondor(expiry, *options, 2, 200, 300, 103, 117)
    instruments = [dict(id=str(uuid4()), chain_symbol=o.symbol, expiration_date=expiry.isoformat(),
                        strike_price=str(o.strike), type=o.option_type, state="active", tradability="tradable",
                        trade_value_multiplier="100", underlying_type="index") for o in options]
    return condor, instruments


class FakeClient:
    def __init__(self, instruments):
        self.instruments = instruments
        self.calls = []
        self.fail_place = False
        self.account = dict(account_number="test-account", agentic_allowed=True,
                            option_level="option_level_3", brokerage_account_type="individual",
                            type="limited_margin", state="active", deactivated=False, permanently_deactivated=False)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "get_accounts":
            return {"data": {"accounts": [self.account]}}
        if name == "get_option_instruments":
            return {"data": {"instruments": self.instruments}}
        if name == "review_option_order":
            return {"data": {"order_checks": [{"detail": "Example broker alert"}]}}
        if self.fail_place:
            raise TimeoutError("Connection lost after send")
        return {"data": {"order": {"state": "queued"}}}


class PayloadTests(unittest.TestCase):
    def test_schema_and_explicit_price(self):
        c, rows = fixture()
        payload = build_live_payload(c, account_number="a", instruments=rows, limit_price="1.75")
        self.assertEqual(payload["price"], "1.75")
        self.assertEqual(payload["quantity"], "1")
        self.assertEqual([l["side"] for l in payload["legs"]], ["buy", "sell", "sell", "buy"])
        self.assertEqual(payload["direction"], "credit")

    def test_invalid_prices_quantity_and_risk(self):
        c, rows = fixture()
        for args in [dict(limit_price="NaN"), dict(limit_price="Infinity"), dict(limit_price="0"),
                     dict(limit_price="5"), dict(limit_price="1", quantity=True),
                     dict(limit_price="1", quantity=2), dict(limit_price="1", max_risk=0)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_live_payload(c, account_number="a", instruments=rows, **args)

    def test_contract_identity_and_status(self):
        c, rows = fixture()
        for key, value in [("state", "expired"), ("tradability", "untradable"),
                           ("trade_value_multiplier", "10"), ("chain_symbol", "SPXW")]:
            invalid = [dict(r) for r in rows]
            invalid[0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                build_live_payload(c, account_number="a", instruments=invalid, limit_price="2")

    def test_mismatched_condor_and_duplicate_contracts(self):
        c, rows = fixture()
        for invalid in [replace(c, long_put=replace(c.long_put, symbol="SPXW")),
                        replace(c, long_put=replace(c.long_put, strike=110))]:
            with self.assertRaises(ValueError):
                build_live_payload(invalid, account_number="a", instruments=rows, limit_price="2")
        rows[1]["id"] = rows[0]["id"]
        with self.assertRaises(ValueError):
            build_live_payload(c, account_number="a", instruments=rows, limit_price="2")

    def test_error_response_rejected(self):
        for result in [{"isError": True, "data": {}}, {}, {"data": None}]:
            with self.assertRaises(RuntimeError):
                unwrap(result)


class ExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.condor, rows = fixture()
        self.client = FakeClient(rows)
        self.now = 100
        self.gate = True
        self.executor = LiveOptionExecutor(self.client, journal_path=self.tmp.name + "/orders.db",
                                          entry_gate=self.entry_gate, enabled=True, clock=lambda: self.now)

    async def entry_gate(self):
        return self.gate

    async def asyncTearDown(self):
        self.executor.close()
        self.tmp.cleanup()

    async def review(self):
        return await self.executor.review(self.condor, account_number="test-account", limit_price="2")

    def placements(self):
        return [args for name, args in self.client.calls if name == "place_option_order"]

    async def test_review_never_places_and_preserves_alerts(self):
        ticket = await self.review()
        self.assertEqual(ticket["review"]["order_checks"][0]["detail"], "Example broker alert")
        self.assertEqual(self.placements(), [])

    async def test_confirmation_required(self):
        ticket = await self.review()
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"])
        self.assertEqual(self.placements(), [])

    async def test_exact_reviewed_payload_submitted_once(self):
        ticket = await self.review()
        ticket["payload"]["price"] = "4"  # External mutation cannot change stored order.
        result = await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(result["order"]["state"], "queued")
        self.assertEqual(self.placements()[0]["price"], "2")
        self.assertEqual(self.placements()[0]["ref_id"], ticket["ref_id"])
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(len(self.placements()), 1)

    async def test_expired_review(self):
        ticket = await self.review()
        self.now += 31
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(self.placements(), [])

    async def test_permissions_rechecked_before_submit(self):
        ticket = await self.review()
        self.client.account["agentic_allowed"] = False
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(self.placements(), [])

    async def test_rejects_cash_retirement_lower_options_permissions(self):
        for key, value in [("type", "cash"), ("brokerage_account_type", "ira_roth"),
                           ("user_option_level", "option_level_2"), ("state", "restricted")]:
            original = dict(self.client.account)
            self.client.account[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                await self.review()
            self.client.account = original

    async def test_disabled_executor(self):
        self.executor.enabled = False
        with self.assertRaises(RuntimeError):
            await self.review()
        self.assertEqual(self.client.calls, [])

    async def test_gate_rechecked_before_submission(self):
        ticket = await self.review()
        self.gate = False
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(self.placements(), [])

    async def test_uncertain_submission_cannot_be_repeated_after_restart(self):
        ticket = await self.review()
        self.client.fail_place = True
        with self.assertRaises(TimeoutError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.executor.close()
        self.executor = LiveOptionExecutor(self.client, journal_path=self.tmp.name + "/orders.db",
                                          entry_gate=self.entry_gate, enabled=True, clock=lambda: self.now)
        with self.assertRaises(RuntimeError):
            await self.executor.submit(ticket["ref_id"], confirmed=True)
        self.assertEqual(len(self.placements()), 1)
