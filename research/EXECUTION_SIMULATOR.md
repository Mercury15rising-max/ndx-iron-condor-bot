# Offline execution simulator

Run: python -m unittest discover -s research -p 'test_*.py'

ExecutionSimulator stores synthetic package events and state in SQLite transactions. Event IDs are idempotent; conflicting duplicate IDs fail. Order IDs cannot be reused. Unresolved submissions or timeouts block another submission. Restart reloads the unresolved state. Rejected exits preserve the open position. A halt blocks new entries but permits exits from a reconciled position.

One-package entry limit: partial package fills cannot occur with integer one-lot quantities. An individual-leg mismatch instead halts and marks reconciliation required; this model cannot manage individual-leg exposure. It must not be treated as proof that broker multileg fills are atomic. No automatic retry, inferred fill, or invented execution price is used.

Tests cover filled entry/exit, rejected entry/exit, duplicate reports, timeout then restart and reconciliation, fractional package rejection, leg mismatch halt, invalid risk and transaction rollback. Current total research suite: 24 passing tests.

This simulator has no broker integration or live enable switch. It does not model fill prices, commissions, net P&L, quote-driven exits, assignment, continuous monitoring or actual account state. The $30 entry bound is a synthetic fixture guard; production risk enforcement is not implemented here. The existing PaperLedger separately enforces the simulated account/day/entry limits. They are not yet integrated into a complete execution engine.

Next remaining milestone: price-based simulated execution and exit accounting integrated with PaperLedger, followed by fresh market-session data validation. These tests do not establish live readiness or profitability. No production deployment or real orders are included.
