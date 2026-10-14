# NDXP four-leg credit paper pipeline

Supported archived strategies: `iron_condor` and `iron_butterfly` (short iron
butterfly). These use the existing strategy leg roles and configured credit
exit/risk limits. The pipeline validates an explicit four-leg selection from a
complete exported universe. It does not choose or replace legs automatically,
and it does not call the midpoint-based builders to claim executable prices.
This is an execution/accounting test, not a new EMA signal definition or a
live brokerage client. One contract per leg, multiplier 100, one position.

## Exact bundle schema

Top level is unchanged:

* `version`: integer `1`.
* `observed_at`: timezone-aware ISO actual data observation timestamp.
* `source`: `{ "kind": "observed", "name": "provider/export identity" }` for
  real read-only data, or explicitly `"kind": "fixture"` for synthetic tests.
* `candles`: ordered QQQ five-minute bars. Each has `symbol: "QQQ"`,
  `timeframe_seconds: 300`, `closed: true`, timezone-aware `close_time`, and
  finite numeric/numeric-string `open`, `high`, `low`, `close`, `volume`.
  `0 < low <= min(open,close) <= max(open,close) <= high`, volume >=0,
  no interpolation. For entry, three complete exchange sessions plus latest
  completed current bars are required; latest close <=300 seconds old.
  No missing, duplicated, misaligned, or skipped-session bars.
* `options`: object containing `complete`, `selection`, `chains`, `instruments`,
  and `quotes` described below. Provider metadata in these rows is preserved.

New `options.selection`:

```json
{
  "strategy": "iron_condor",
  "legs": {
    "long_put": "ACTUAL_LONG_PUT_INSTRUMENT_ID",
    "short_put": "ACTUAL_SHORT_PUT_INSTRUMENT_ID",
    "short_call": "ACTUAL_SHORT_CALL_INSTRUMENT_ID",
    "long_call": "ACTUAL_LONG_CALL_INSTRUMENT_ID"
  }
}
```

Use `"iron_butterfly"` for a short iron butterfly. This example is a schema
illustration, not market data. Four IDs must be distinct, and no extra leg roles
are accepted. No 0DTE or leg substitution.

`options.complete`: boolean, true only after finished provider pagination and
quote requests for the exported universe; otherwise no entry.

Each selected chain row requires:

* `id`: unique nonempty string.
* `symbol: "NDXP"`, `settle_on_open: false`, `can_open_position: true`.
* `trade_value_multiplier`: numeric value or numeric string equal to `100`.

Each selected instrument row requires:

* `id`: unique nonempty string; `chain_id`: selected chain ID.
* `chain_symbol: "NDXP"`, `state: "active"`, `tradability: "tradable"`.
* `type`: `"put"` for put roles, `"call"` for call roles.
* `expiration_date`: same ISO date on all four, strictly after observation's
  New York date and an exchange session. Credit strategies do not inherit the
  debit engine's 1–3-day expiration restriction.
* `strike_price`: positive finite number/string.
* `trade_value_multiplier`: number/string equal to `100`.

All four must share one PM-settled chain and expiration. Condor ordering:
`long_put < short_put < short_call < long_call`. Butterfly ordering:
`long_put < short_put = short_call < long_call`. Both protective widths must
be positive; asymmetric protective wings are allowed and risk uses the wider.

Each quote requires:

* `instrument_id`: unique nonempty string matching instrument ID.
* `updated_at`: original timezone-aware quote timestamp, age 0–60 seconds.
* `bid_price`, `ask_price`: finite numbers/strings, `0 < bid <= ask`.
* `bid_size`, `ask_size`: finite numbers/strings >=1.
* `delta` and additional provider fields may be preserved but are not required
  for explicit credit-leg selection. No generated timestamps or invented sizes.

All four entry quotes must be valid. Exit quotes must also be newer than entry.
Exits use persisted contract metadata and IDs, never the latest selection. All
four must be executable observations in one snapshot; unavailable legs leave
the whole position unresolved with cash/position unchanged. No partial exits.
Entry history is not required to process a previously opened position's exit.
The local pinned XNAS/XNYS-alias calendar verifies regular hours, holidays and
early closes; input calendar assertions are not trusted.

## Fees, risk, and whole-position exits

Prices below are option points; cash figures use multiplier 100 and quantity 1.
Let S be the two shorts and L the two wings:

* Gross entry credit `G = 100 * (sum(S.bid) - sum(L.ask))`.
* Entry fee `Fe = 4 * fee_per_contract`; modeled exit fee `Fx` uses the same
  explicit per-contract fee. Default $0.50 per leg per side ($2 each side).
* Net entry cash credit `E = G - Fe`; both G and E must be positive.
* Wider protective width cash
  `W = 100 * max(short_put-long_put, long_call-short_call)`.
* Fee-inclusive maximum loss `Lmax = W - G + Fe + Fx`. Reject gross credit
  >=W and nonpositive credit. This is the expiration-payoff risk plus modeled
  fees, not a guaranteed liquidation loss cap: adverse observed quote-side
  exits can overshoot, and losses are never clipped or fabricated.
* Gross exit debit `D = 100 * (sum(S.ask) - sum(L.bid))`.
* Total exit cost `X = D + Fx`; realized P&L `E-X`.

On entry, credit is added to simulated cash; on whole-position exit, X is
subtracted. Accounting independently recomputes all four quote sides, fees,
maximum loss, cash, position identity, completed count and daily realized P&L.
Replay records every snapshot/event with exact source/config fingerprints.

Credit stop: close the entire position when
`D >= G * STOP_LOSS_MULTIPLE` (default 2.0). Thus stop-trigger net loss is
`G*(multiple-1)+Fe+Fx` before observation overshoot. It is not the debit engine's
30%-of-entry-cost stop. Profit target uses
`D <= G*(1-PROFIT_TARGET_PCT/100)` (default 50%). Thresholds use gross cash
values, consistent with the configured credit exit policy; fees always affect
cash and P&L. A negative observed D means a modeled credit on liquidation and
is recorded as observed rather than clamped to zero.

Exit priority: configured daily-loss kill switch, credit stop, profit target,
then time exit. Time exit starts at configured `EXIT_ONLY_START` or 30 minutes
before verified session close, whichever occurs first, including early closes.
If data is unavailable, retain UNRESOLVED even after an exit threshold; no
guaranteed fill, settlement inference, or continuous stop protection is claimed.

Risk parameters are captured from existing Settings when initializing a credit
archive: MAX_RISK_PER_TRADE (500), MAX_DAILY_LOSS (750), MAX_OPEN_POSITIONS (1),
MAX_TRADES_PER_DAY (1), MAX_TOTAL_OPEN_RISK (750), MAX_POSITIONS_PER_FAMILY (1),
profit/stop thresholds and entry/exit windows. Defaults shown are repository
defaults; runtime overrides are captured. Lmax must not exceed per-trade risk,
total-open-risk allowance, or pre-entry simulated cash. No concurrent positions
are supported. The archive freezes risk/fees/strategy for reproducible replay;
later environment changes do not silently alter the experiment. A 30-trade
review gate remains, and no result promotes the engine to live trading.

## Running and data separation

```bash
source .venv/bin/activate
export TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false ALLOW_0DTE=false
python paper_pipeline.py observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json \
  --strategy iron_condor --fee-per-contract 0.50 --init
python paper_pipeline.py next-observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json
python paper_replay.py /workspace/ndxp-state/condor-archive.json
```

For butterfly, initialize a separate archive with `--strategy iron_butterfly`.
Use --init only for a genuinely absent archive. Existing archives retain their
strategy and fees; conflicting CLI overrides are rejected. Keep the existing
debit-spread archive separate. Code fingerprint changes mean old archives must
be replayed with their original code version; no migration/reset is performed.

Fixture runs require `--historical --allow-fixtures`, source.kind=fixture, and
a separately named fixture archive. CLI rejects fixture/observed source mixing
and resets. No observed bundle is generated from synthetic data. Forward
observations must be <=60 seconds old; offline historical observations must
explicitly use --historical and retain their original timestamps.

The authenticated read-only Robinhood Trading MCP connection is still unavailable
in this environment: get_equity_historicals, get_option_chains,
get_option_instruments and get_option_quotes are not exposed. No actual candle
or option data, broker fills, or observed-market paper trade has been validated.
Official Nasdaq calendar confirmation also remains blocked; the pinned
third-party calendar passed local holiday/early-close regressions. No order tools
are called, no scheduler/deployed worker was changed, and no deployment occurred.
