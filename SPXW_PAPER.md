# SPXW overnight paper strategy

`spxw_paper.py` implements the mechanical call-debit-spread experiment. It has no
brokerage client or order methods. It is separate from the existing credit-spread
exit logic and does not start from the Railway heartbeat worker.

## Fixed rules

- Start with $3,000 simulated cash; one one-lot spread open at a time.
- PM-settled SPXW, extended hours enabled, 100 multiplier, 1–3 calendar days
  remaining relative to the Chicago calendar date. No 0DTE entries.
- Select the earliest eligible expiry. Among fresh, valid calls, select delta
  nearest 0.30; ties favor lower strike, then contract ID. Sell the call exactly
  five points higher on the same chain and expiry. Skip if that leg is unavailable.
- Entry = (long ask − short bid) × 100 + $2 modeled fees. Premium must be positive;
  total entry must be <= $150 and affordable. Do not substitute a cheaper spread
  after the selected spread fails the cost limit.
- Both legs need positive, uncrossed quotes, bid/ask sizes >= 1, and timestamps
  between zero and 60 seconds old. Future, missing and invalid values are rejected.
- Exit value = (long bid − short ask) × 100 − $2 modeled fees.
- Stop when exit value minus total entry cost <= −30% of total entry cost.
  Close both legs hypothetically at observed prices. Do not cap losses at 30%.
- Otherwise exit at the first valid observation >= 60 minutes after entry.
  Stop classification takes priority when both conditions apply.
- Missing exit data leaves the position unresolved and blocks new entries.
- Stop new entries after $300 realized losses per overnight trading session;
  evening and following morning share the next business trading-date key.
- Stop new entries after 30 completed paper trades for review.

The engine only evaluates when invoked. With hourly snapshots the stop may
merely classify the same exit as the time rule. There is no continuous protection,
broker-held stop, guaranteed stop price, or profitability claim. Fees are explicit
simulation assumptions, not a verified broker fee schedule. Simultaneous fills
at the displayed leg prices are a model, not evidence of real spread execution.

## Feed contract

Supply a JSON object with:

- `chains`: the `data.chains` array from read-only `get_option_chains`.
- `instruments`: fully paginated `data.instruments` for the eligible PM-settled
  SPXW call expirations. Include chain ID, ID, strike, expiration, type, state,
  tradability, chain symbol, and multiplier.
- `quotes`: quote objects extracted from `data.results[].quote`, matched by
  instrument ID. Preserve original source timestamps, deltas and displayed sizes.
- `complete: true`: only after contract pagination and quote retrieval have
  completed. Never label a partial search complete.
- `session_open: true` and timezone-aware `session_observed_at`: verified from
  the current exchange session/calendar including holiday exceptions. This
  assertion must also be <=60 seconds old. Do not manufacture a fresh timestamp
  to make an old market status or quote pass. The engine additionally enforces
  the normal Sunday–Thursday evening / Monday–Friday morning Chicago window
  (19:15–08:25). A bare weekday check does not override exchange closures.

No authenticated feed collector is bundled. A supported read-only client must
produce this snapshot; the ChatGPT connection is not inherited by Railway.
Until that integration exists, this is a runnable snapshot engine, not an
unattended overnight trader. Do not build a custom Robinhood OAuth callback as
a workaround for unsupported hosted integrations.

## Run on Linux/macOS

For a genuinely new experiment, after obtaining a verified snapshot:

```bash
TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false python spxw_paper.py snapshot.json --init
```

For subsequent fresh snapshots (including after a restart):

```bash
TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false python spxw_paper.py snapshot.json
```

The default ledger is `data/spxw_paper_state.json`. Keep this file on durable
storage when hosting. `--state PATH` selects a ledger. A missing ledger requires
explicit initialization; `--init` refuses to overwrite an existing ledger.
Never initialize another ledger to bypass an unresolved position or risk limit.
The CLI uses an exclusive file lock and atomically replaces the ledger, storing
the position, cash, realized session P&L, completed count and audit events together.
Corrupt state raises an error instead of silently resetting the balance.
`balance` is available paper cash, not marked-to-market account equity when open.

Each event records its decision, observation time and paper-only status. Entries
and exits include the contract IDs, original metadata, quotes, fees and prices.
Exits additionally record net P&L, threshold and overshoot. Replayed or backwards
observation times are rejected. No production scheduler or environment settings
are changed by importing this module.

## Verify

```bash
python -m unittest discover -s tests -v
```

The new tests use synthetic quotes and dates. Passing tests validate the code's
rules and persistence behavior, not live feed availability or strategy returns.
