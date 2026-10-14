# Deterministic NDX paper validation goal

Complete 30 paper trades under one fixed version/configuration, with every recorded
observation replaying exactly and every entry/exit/cash calculation independently
reconciled. Do not force trades to meet this count. No-data/no-signal observations
remain recorded. This is an engineering milestone, not evidence of future profit.

Use paper_replay.py as the observation runner for this experiment; it calls the
NDX engine and stores inputs and outputs together in a locked, atomically replaced
archive. Do not alternate with the separate ndx_paper.py ledger or start duplicate
experiments against an existing position. Existing ledgers cannot be imported
without their original snapshots; no continuity is fabricated.

    python paper_replay.py data/ndx_replay.json --init
    python paper_replay.py data/ndx_replay.json --snapshot snapshot.json --observed-at 2026-10-14T13:00:00-04:00
    python paper_replay.py data/ndx_replay.json

The last command verifies/reports only. Observed-at must be actual observation time
for forward paper tests; historical times are for explicitly offline replay. No
scheduler or feed is installed. Archive snapshots must contain market data only,
never credentials or account secrets. This runner makes no network/order calls.

Records include contiguous sequence numbers, hash links, complete snapshots,
explicit times, exact events, state hashes, configuration and source fingerprint.
Reordered, edited or internally missing records fail checks; code changes require
the original code version to replay an old archive. Hashes are not signatures:
someone able to rewrite the entire archive can recompute them, and removal of the
last records cannot be detected without an externally retained final hash/count.
This is corruption detection, not an authenticated tamper-proof ledger.

Independent accounting recomputes entry/exit cash from quote sides and fees,
checks ledger balance/completed count/position presence, and reports realized P&L,
mean net P&L, win rate and closed-trade drawdown. Drawdown excludes intratrade
mark-to-market losses. Open positions are flagged; cash is not account equity.

A post-trade stress column subtracts $20 per completed round-trip: $0.05 option
price points adverse on each of two legs at entry and exit, multiplier 100.
It does not rerun entry affordability, stop timing or liquidity. It is sensitivity
analysis only, not a new execution simulation or a hypothetical fill claim.

At 30 completed trades and no open position, status becomes REVIEW_REQUIRED.
Review net results, stress sensitivity, drawdowns, unresolved/data gaps and rule
compliance before selecting a separate out-of-sample test. Negative results call
for review, not automatic parameter tuning. No auto-promotion to live trading and
no target dollar profit. The engine's existing risk limits remain unchanged.

This PR adds original Python replay/accounting code inspired by general simulator
architecture. No ApexHFT code or claimed benchmark results are incorporated.
