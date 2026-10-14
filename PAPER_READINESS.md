# Quentin Simmons Jr Trading Bot: paper-test readiness

Update: the first observed condor experiment now implements fixed deterministic
selection rules in FIXED_CONDOR_EXPERIMENT.md. The selector inspection below
describes the earlier gaps and legacy functions. For this condor experiment those
gaps are resolved by earliest 1–7 DTE, inclusive .10–.15 short deltas, highest put/
lowest call short strikes, exact symmetric 25-point wings, ambiguity rejection
and no butterfly fallback. Real-data plan validation remains blocked, so no plan
or observed archive has been created. Automatic butterfly selection is unchanged.

## Verified and enforced joint risk

Verified runtime Settings: $500 maximum loss per trade; $750 daily realized-loss
limit; $750 total open risk; one open position; one trade per New York day.
Profit target remains 50%, stop debit multiple 2, entry window 10:00–14:30 New
York, exit-only 15:30 or 30 minutes before verified early close. Credit pipeline
initialization refuses archives/configurations that differ from these five
verified limits, rather than silently loosening portfolio controls.

Observed iron-condor and iron-butterfly archives now MUST share
`/workspace/ndxp-state/observed-portfolio.sqlite3`. There is no observed-data
override to select an independent database. A portfolio-wide filesystem lock
serializes both strategies; SQLite transactions durably store canonical archives.
Every entry decision reconciles registered positions, summed fee-inclusive open
risk, daily realized P&L, daily entry count, and shared simulated cash from all
registered archives. Simulated cash starts once at $3000, not $3000 per strategy.
The engine records the aggregate risk context in each observation for exact
replay. Even an unresolved prior-day position blocks a new strategy entry.

JSON archives are replayable exports of the canonical committed database state.
An interruption after SQLite commit but before JSON export is recovered on the
next run without duplicating entry/cash. Only a known previous export is repaired;
an externally modified/missing registered archive is rejected. Keep the database,
its lock file and every registered archive together; do not delete portfolio state
or copy/rename archives to start a fresh account. No remote or distributed
coordinator is provided: supported concurrent runs must share this filesystem.

Existing archives are preserved. Archives with old source fingerprints must be
replayed with the original commit/dependencies. Unregistered archives with history
are refused by the new portfolio; no automatic adoption, loss-history reset, or
duplicate cash is inferred. A separate audited registration/migration would be
needed to continue them. Pure engine functions remain unit-test primitives; bot
credit observations must use paper_pipeline.py. paper_replay.py refuses credit
--snapshot writes and remains a read-only validator for credit archives.

Fixtures use a separate `fixture-portfolio.sqlite3` by default beside their
archives; `--portfolio` can group fixtures across directories in one isolated
database. Fixture and observed modes cannot share a database. Production credit
state is not shared with the legacy call-debit-spread experiment: do not treat
that separate engine as an additional position in this credit experiment.

## Contract-selection inspection: existing rules and missing automation

The following are inspected rules, not a claim that the pipeline automatically
executes them:

| Selector | Existing behavior | Missing/ambiguous rule |
| --- | --- | --- |
| expiration_selector.choose_expiration | Earliest expiration inside supplied min/max DTE (defaults 1–7), excluding 0DTE | Credit pipeline does not invoke it; no frozen DTE window was specified for credit experiments |
| strategy.build_iron_condor | Puts/calls with absolute delta in supplied interval (default .10–.15); highest put short strike, lowest call short strike | Equal-strike/duplicate-instrument ties use input order; upstream single chain/expiry is assumed |
| Condor wings | Nearest strike to short ± requested wing width (default 25), strictly protective side | Equal-distance ties use feed order; exact width versus nearest permissible width and asymmetry were not fixed |
| butterfly_strategy.build_iron_butterfly | Nearest put/call to caller's center, require equal short strikes; nearest protective wings | Source of butterfly center is missing; equal-distance and duplicate-contract ties use input order |
| strategy_selector.select_best_strategy | Largest reward/risk score; condor appended before butterfly | Equal-score butterfly candidates depend on supplied loop/input order; uses mid prices and ignores pipeline fees |
| select_strategy_for_regime | Regime chooses family; neutral high IV → condor, neutral contained IV → butterfly | Frozen source/version for direction/volatility/confidence, center source, candidate grids and stable ties missing |
| credit pipeline | Supplied strategy and four exact instrument IDs; chain/expiry/strike/quote validation | No automatic expiration, short strike, wing width or cross-strategy chooser is wired in |

Do not initialize an automatically selected observed experiment while these
rules are unspecified. This change does NOT invent a new automatic selection
algorithm or silently reuse midpoint scores as executable quote credits.

The supported deterministic test is a **frozen explicit contract plan**. Before
observed credit initialization, supply `--selection-plan` with strategy, four
distinct contract IDs and nonempty documentation of all five selection rules.
Those IDs and strategy are the actual deterministic selection: no candidates,
ties, rolling expiry, substitute wings or implicit condor/butterfly fallback.
Validate their metadata against the real export; nonempty description text is
documentation, not proof an external selection algorithm is implemented.
The plan is frozen in the canonical portfolio. Entry IDs must match it and
later plan changes are rejected. Exits always use the open position's IDs.
This explicit plan covers its one selected expiration; automatic rolling and a
multi-expiration research experiment remain unspecified and are not enabled.

Selection-plan schema (illustrative placeholders, not observed data):

```json
{
  "mode": "explicit_contract_plan",
  "strategy": "iron_condor",
  "legs": {
    "long_put": "ACTUAL_LONG_PUT_ID",
    "short_put": "ACTUAL_SHORT_PUT_ID",
    "short_call": "ACTUAL_SHORT_CALL_ID",
    "long_call": "ACTUAL_LONG_CALL_ID"
  },
  "expiration_rule": "Fixed actual YYYY-MM-DD expiration; document why it was chosen",
  "short_strike_rule": "Fixed actual put/call short IDs; document strikes and selection criterion",
  "wing_width_rule": "Fixed actual protective IDs; document both widths",
  "tie_break_rule": "No ranking ties in the explicit-ID plan; document any upstream tie-break",
  "strategy_rule": "Fixed iron_condor for this archive; no implicit strategy fallback"
}
```

Use iron_butterfly and its actual four IDs for a butterfly plan. The complete
observed bundle schema, four-leg quote-side fees/stop/max-loss formulas and
metadata requirements are in CREDIT_PAPER_SCHEMA.md. options.selection.strategy
and options.selection.legs must agree with the plan. Do not fabricate missing
provider sizes, timestamps, metadata or completeness assertions.

## Exact observed import and replay commands

Run in `/workspace/ndx-iron-condor-bot`:

```bash
source .venv/bin/activate
export TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false ALLOW_0DTE=false

# Only for a genuinely NEW condor archive, with a completed explicit plan:
python paper_pipeline.py observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json \
  --strategy iron_condor --fee-per-contract 0.50 \
  --selection-plan /workspace/ndxp-state/condor-selection-plan.json --init

# Subsequent observations reuse both the archive and shared portfolio:
python paper_pipeline.py next-observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json

python paper_replay.py /workspace/ndxp-state/condor-archive.json
```

Forward data must have actual observed_at no more than 60 seconds old, the most
recent candle close <=300 seconds old and original option quotes <=60 seconds old.
For an actual HISTORICAL export use the same command with `--historical`:

```bash
python paper_pipeline.py observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json \
  --strategy iron_condor --fee-per-contract 0.50 \
  --selection-plan /workspace/ndxp-state/condor-selection-plan.json \
  --historical --init
python paper_replay.py /workspace/ndxp-state/condor-archive.json
```

Omit --init if the archive already exists, and omit unchanged strategy/fee/plan
arguments on later observations. An old/unregistered archive must not be reset
or automatically reinitialized if it is rejected. Keep original quote and candle
times; --historical bypasses only wall-clock recency, not quote freshness relative
to the observation. Submit both strategies' history in global chronological order;
backdated observations are rejected. Equal observation times are serialized in
arrival/lock order and recorded; this is not a deterministic strategy chooser.

For a butterfly substitute `--strategy iron_butterfly`, butterfly archive path
and its plan. It automatically uses the SAME observed portfolio; combined risk,
entry count and open position remain jointly limited.

## Remaining external blockers and validation scope

No callable Robinhood Trading MCP data tools are present. Runtime has no
ROBINHOOD_MCP_URL, ROBINHOOD_TOKEN_PATH, PUBLIC_BASE_URL or AUTH_SETUP_KEY binding,
and no OAuth token file at the default /data/robinhood_oauth.json. A configured
repository client is not an authenticated connection. Required read-only tools:
get_equity_historicals (QQQ 5-minute, ≥3 completed sessions), get_option_chains,
get_option_instruments and get_option_quotes (PM-settled NDXP metadata and
timestamped bid/ask with sizes). No order calls are needed or authorized.

No observed-bundle.json or real-market paper-trade archive was created. Synthetic
regressions exercise persistence, recovery, concurrent strategy runs, aggregate
limits, and accounting; they are not actual market fills or strategy evidence.
Official Nasdaq schedule verification remains blocked; pinned third-party
XNAS/XNYS-alias holiday, early-close and DST checks are local verification only.

GitHub pull-request API access returned Forbidden; changes can be committed
locally but no PR link is available. No scheduler or deployed bot is changed,
and no deployment occurred. Live orders and 0DTE remain disabled.
