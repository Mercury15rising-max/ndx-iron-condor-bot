import unittest
from datetime import datetime, timedelta, timezone

from safety_gate import evaluate_entry_safety
from zero_dte_policy import ZeroDTEPolicy, validate_zero_dte_request


class SafetyGateTests(unittest.TestCase):
    def test_rejects_stale_quotes(self):
        now = datetime.now(timezone.utc)
        result = evaluate_entry_safety(
            quote_timestamp=now - timedelta(seconds=45),
            now=now,
            max_quote_age_seconds=30,
        )
        self.assertEqual(result.action, "reject")

    def test_kill_switch_after_consecutive_losses(self):
        now = datetime.now(timezone.utc)
        result = evaluate_entry_safety(
            quote_timestamp=now,
            now=now,
            consecutive_losses=2,
            max_consecutive_losses=2,
        )
        self.assertEqual(result.action, "kill_switch")

    def test_fresh_quote_passes(self):
        now = datetime.now(timezone.utc)
        result = evaluate_entry_safety(
            quote_timestamp=now - timedelta(seconds=5),
            now=now,
        )
        self.assertEqual(result.action, "allow")


class ZeroDTEPolicyTests(unittest.TestCase):
    def test_spxw_can_be_enabled_for_paper_only(self):
        policy = ZeroDTEPolicy(enabled=True)
        allowed, _ = validate_zero_dte_request(
            chain_symbol="SPXW",
            trading_mode="paper",
            live_orders_enabled=False,
            policy=policy,
        )
        self.assertTrue(allowed)

    def test_live_mode_is_rejected(self):
        policy = ZeroDTEPolicy(enabled=True)
        allowed, _ = validate_zero_dte_request(
            chain_symbol="SPXW",
            trading_mode="live",
            live_orders_enabled=True,
            policy=policy,
        )
        self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
