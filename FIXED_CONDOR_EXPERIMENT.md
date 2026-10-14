# First paper-only NDXP iron condor experiment

Ruleset `fixed_ndxp_condor_v1` implements the user-specified selection rules.
New observed iron-condor archives default to this ruleset and cannot opt out.
Existing archive source/config fingerprints are preserved; use original code to
replay old archives rather than resetting or silently migrating them.

1. Eligible chains are active for opening, PM-settled (`settle_on_open=false`),
   symbol NDXP, multiplier 100. Instruments must be active/tradable with matching
   chain, symbol, type and multiplier.
2. Choose the earliest available expiration 1–7 calendar days after the New York
   observation date, and require an exchange-session expiry. Exclude 0DTE. Choose
   expiration before checking availability of delta-qualified legs/wings. Do not
   fall back to a later expiration when its contracts are unusable.
3. Short absolute deltas must be .10–.15 inclusive. Pick highest qualifying put
   strike and lowest qualifying call strike; require put short < call short.
4. Long put must be exactly 25 points below short put; long call exactly 25 points
   above short call. No nearest-strike, asymmetric, wider/narrower substitutes.
5. Reject duplicate IDs and distinct tradable contracts sharing the same chain,
   expiration, option type and numeric strike. Selection is independent of row
   ordering. Multiple eligible PM chains at the earliest expiration are rejected
   as an unresolved chain choice; no unrequested chain-ranking rule is invented.
6. In the chosen expiration, missing delta/quote data prevents proving the short
   ranking, so selection fails closed. All four selected quotes must have original
   timestamps age 0–60 seconds, positive uncrossed bid/ask, sizes >=1. Never select
   lower-ranked shorts to bypass stale/missing quotes on the chosen shorts.
7. Iron condor only; no butterfly fallback. Retain $500 fee-inclusive per-trade
   loss bound and the shared $750 daily/$750 open-risk/one-position/one-entry limits.
   Valid observations with missing exact wings or exceeded limits are archived as
   NO_TRADE; no leg or fill is substituted. Structurally invalid data may be
   rejected by the importer before observation recording.

Entry/exit sides, explicit modeled fees, maximum loss and credit stop calculation
remain as documented in CREDIT_PAPER_SCHEMA.md. With 25-point wings and modeled
$2 entry plus $2 exit fees, maximum loss is `2500 - gross_credit + 4`. Therefore
the $500 bound requires gross credit >=$2004. Most snapshots may legitimately
produce NO_TRADE; neither widths nor risk limits are relaxed to force a trade.

## Actual-data validation before plan creation

No actual data is supplied by the selector. Require a genuine exported bundle
using the exact schema in CREDIT_PAPER_SCHEMA.md: named observed provenance,
QQQ 5-minute history for ≥3 completed sessions and current bars, complete NDXP
contracts/quotes, original quote times/sizes and deltas for all contracts needed
to rank shorts. Never relabel fixtures as observed data. Provider pagination must
be complete; the importer cannot independently authenticate a manually labeled
file as a Robinhood response.

Run from /workspace/ndx-iron-condor-bot:

```bash
source .venv/bin/activate
export TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false ALLOW_0DTE=false

# Only after ACTUAL exported data is available. No archive is initialized here.
python condor_selection.py observed-bundle.json \
  --plan /workspace/ndxp-state/condor-selection-plan.json --historical
```

Use --historical only for actual historical exports, preserving original times.
Forward observations must be <=60 seconds old. The command rejects fixtures,
checks history/quotes/selection and all available shared risk state, and creates
a new plan only after a qualifying entry validation. If selection/risk prevents
entry, it reports NO_TRADE and creates no plan. It refuses to overwrite an
existing plan. PLAN_VALIDATED is validation only, not a recorded trade or fill.
Plan validation does not reserve shared capacity; entry risk is checked again
atomically under the portfolio lock during import.

The resulting explicit-ID plan contains ruleset `fixed_ndxp_condor_v1`, strategy,
four actual provider IDs and the five rule descriptions. Do not create that file
with invented IDs or from a synthetic fixture. Only the validated first contract
set may open in this experiment; a later rule-selected set that differs from the
frozen plan produces NO_TRADE. Automatic rolling to a new plan is not enabled.

```bash
# Genuinely new archive only; omit --init on all later observations.
python paper_pipeline.py observed-bundle.json \
  --archive /workspace/ndxp-state/condor-archive.json \
  --strategy iron_condor --selection-rules fixed_ndxp_condor_v1 \
  --fee-per-contract 0.50 \
  --selection-plan /workspace/ndxp-state/condor-selection-plan.json \
  --historical --init
python paper_replay.py /workspace/ndxp-state/condor-archive.json
```

Exits always use the entire persisted position, even if the current universe no
longer contains the selected contracts. Original newer exit quotes are still
mandatory. Selection failures cannot cause an open position to be substituted.

## Current blocker

No authenticated read-only Robinhood Trading MCP tools or OAuth token file are
available in this environment, and observed-bundle.json is absent. Accordingly,
condor-selection-plan.json was NOT created and no observed archive was initialized.
Tests use synthetic data solely for regression checks, not observed-market paper
trades. Official Nasdaq calendar confirmation remains unverified externally.
No order calls, scheduler changes or deployment occur.
