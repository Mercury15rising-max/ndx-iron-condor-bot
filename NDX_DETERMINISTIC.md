# NDXP deterministic paper baseline v1

Purpose: identical snapshots + ledger + observation time produce identical decisions.
A 30-completed-trade research sample is a stopping point for review, not a promise
of profitability or sufficient statistical validation. No live trading or worker
changes. This standalone engine depends on the EMA module from PR #4.

NDX is an index; this engine models PM-settled NDXP options, not stock shares.
Reference: https://www.nasdaq.com/products/north-american-markets/nasdaq-100-options-xnd-ndx

## Fixed rules

- $3,000 simulated cash, one spread open, one entry per New York calendar day.
- Verified exchange-open assertion observed within 60 seconds; weekday regular
  session 09:30-16:00 New York. Entries only 10:00 through before 14:30.
  Feed adapter must account for holidays/early closes; wall-clock rules alone
  are insufficient. Exits require a verified open session and fresh quotes.
- Explicit QQQ proxy: 106 contiguous completed 5-minute candles, latest no more
  than 5 minutes old. First-close-seeded EMA8 > EMA13 > EMA21 newly established
  relative to previous candle. Bullish only; no position for bearish/neutral.
  QQQ is a proxy and is not the NDX index. Regular-session history now accepts
  exchange-calendar-verified session boundaries, while rejecting intraday gaps,
  skipped sessions and extended-hours bars. Never fill overnight gaps. See
  PAPER_PIPELINE_REVIEW.md for data ingestion and calendar verification limits.
- Earliest eligible PM-settled NDXP expiry 1-3 calendar days away, no 0DTE.
  Long call closest to delta .30, ties lower strike then ID; short exactly 5
  points higher in same chain/expiry. Skip if unavailable; do not substitute width.
- Both quotes positive/uncrossed, sizes >=1, timestamps within 60 seconds.
  Entry = (long ask - short bid)*100 + $2 modeled fees, positive debit and total
  <= $150 and available cash. Hypothetical quote-based fill only.
- Value V = (long bid - short ask)*100 - $2 modeled exit fees.
  P&L = V - recorded entry cost E. Close both legs when P&L <= -0.30E;
  otherwise close at first valid observation >=60 minutes. Stop has priority.
  Report actual observed loss including overshoot. Missing quotes leave unresolved
  position and block new entry. No guaranteed stop fill or continuous protection.
- Keep $300 realized session-loss gate and stop after 30 completed trades.
  No profit target or discretionary override. Quotes/signals/reasons recorded.

## Running

Same snapshot structure as SPXW_PAPER.md, but chain symbol NDXP and signal fields
from EMA_STRATEGY.md with signal_symbol QQQ. Regular-session chains do not need
extended-hours eligibility. A supplied verified calendar/session assertion remains
mandatory. No feed adapter or polling scheduler is supplied by this change.

    python ndx_paper.py snapshot.json --state data/ndx_paper_state.json --init

Subsequent observations omit --init and reuse the same ledger. The engine rejects
SPX ledger files. Process one ordered timestamped observation at a time; state is
locked and atomically replaced. Paper mode and live-orders-disabled are enforced
by CLI. This is a snapshot consumer, not a running autonomous system.

Signals do not combine VWAP or rollback in v1. Keeping one entry definition fixed
makes comparisons meaningful; those alternatives can be separate experiments.
With hourly checks the 30% stop may simply classify the same 60-minute time exit.
For regular-session closure/early close without a usable exit observation, retain
unresolved status rather than inventing a liquidation.
