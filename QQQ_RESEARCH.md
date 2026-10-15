# QQQ research workflow

QQQ is the primary target of this new offline research workflow. Existing index
pipelines, deployment settings, position ledgers and historical archives are unchanged.
This is not a live execution integration or a promise of profitable trades.

## Import and preserve history

Export the QQQ result object from `get_equity_historicals`: `symbol`, `interval`,
`bars`. Request regular-session daily bars, split adjusted, with explicit dates.

```bash
python qqq_research.py research/qqq/seed-daily-2026-10-15.json \
  --source robinhood_mcp.get_equity_historicals:regular:split \
  --as-of 2026-10-15T12:45:00-04:00
```

The seed has 127 completed sessions, April 15 through October 14, 2026. Prices
are provider observations, not independently certified exchange closes. No
account identifiers, holdings, credentials or personal trade records are included.

Imports preserve raw bars in content-addressed JSON, alongside source, capture
time and a versioned report referencing the raw SHA-256. Existing files are never
overwritten. Repeating the exact same record is idempotent. New capture times
create new snapshots even if the underlying bars have not changed. Future-day
and interpolated bars are excluded from calculations; duplicate/unordered dates,
invalid OHLC and insufficient history are rejected. Completeness of exchange
sessions is not certified. More than seven calendar days of staleness blocks
strategy-family nomination. Raw data stays intact for later quality reviews.

## Strategy research

Reuses the bot's existing `ema_signals.ema` first-close seed for EMA 8/13/21.
Reports SMA 20/50/100, a least-squares 20-session slope, 14-session mean true
range and 20-session daily-return standard deviation. Daily bars are not a
substitute for the existing closed five-minute EMA/VWAP/pullback entry signals.

- Bullish: aligned EMAs, close above SMA20 above SMA50, positive slope.
- Bearish: reverse alignment and averages, negative slope.
- Sideways: absolute slope at most 5% of ATR per session and EMA8/EMA21
  separation at most 25% of ATR; research iron condors.
- Mixed or stale: no strategy nomination.

Thresholds are explicit unvalidated hypotheses, not learned probabilities.
Directional regimes nominate existing credit/debit vertical families for research.
The workflow never approves entries, synthesizes option quotes from stock bars,
or infers historical option returns from underlying prices. It does not currently
run the option candidate builders or the intraday entry engine automatically.

`total_risk(per_unit_loss, quantity, total_fees, risk_cap)` requires explicit total
position quantity, estimated entry plus exit fees, and a total budget. It cannot
silently treat a per-condor loss as the whole position's risk. ETF assignment can
create share exposure beyond the intact spread payoff; close all legs together
before expiration if avoiding assignment. Stops do not guarantee fill prices.

## Evidence needed before promoting a strategy

Collect timestamped intraday OHLCV plus contemporaneous option bids/asks,
contract IDs, expirations, strikes, multipliers, Greeks, volume and open interest.
Retain rejected signals and reasons as well as accepted candidates. Archive these
source payloads with `archive_payload`; exclude account data from public git.
Use the existing replay/paper infrastructure for chronological held-out testing
with fees, slippage, stale-data rejection, and assignment-aware exits. Compare
win rate, average profit/loss, drawdown and expectancy net of costs. Select
parameters on training windows only, then evaluate on later unseen periods.

No background collector is installed by this change. Continued data acquisition
needs an authenticated read-only feed in the deployed environment and persistent
storage; a ChatGPT connector session is not inherited by Railway. No live order
transport, deployment or strategy-performance claim is added here.

## Initial archive and validation

Also included: 390 regular-session five-minute QQQ bars (October 8–14), and
one contemporaneous October 15 quote snapshot for four October 16 contracts
(720/721 puts, 728/729 calls), with verified contract metadata. A single options
snapshot is not an options backtest or a complete chain; collect later snapshots
before evaluating exits or profitability.

Validation at base commit `7c37fd3`: five new research tests pass. Full suite:
172 tests, 28 failures and 8 errors. An untouched checkout of the same base ran
167 tests with the exact same 28 failures and 8 errors; no new failing test names.
The pre-existing live/paper configuration failures remain unresolved and block
any claim that the whole bot is validated for deployment.
