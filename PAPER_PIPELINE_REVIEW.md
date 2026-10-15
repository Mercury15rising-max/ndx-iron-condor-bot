# Combined PR review and paper pipeline

Prepared locally on `review/paper-pipeline-integration`; no deployment, remote
merge, push, or order access has occurred. Paper mode is required by the CLIs.

## Dependency order and status evidence

| PR | Tip | Dependency | Fetched main contains tip? | Review |
| --- | --- | --- | --- | --- |
| #3 | e18e7ba | main | No | SPXW paper engine; combined locally |
| #4 | 2b73c8b | #3 | No | EMA/VWAP signals and chart indicator; combined locally |
| #5 | e77a20b | #4 | No | NDXP deterministic engine; combined locally |
| #6 | 9529439 | #5 | No | Snapshot replay/accounting; combined locally |
| #7 | unavailable | unknown | Unknown | Pull ref unavailable; not reviewed |

Fetched `main` is `31c097a`. The new files from #3–#6 are absent from that
branch. Both GitHub REST and GraphQL returned Forbidden, so OPEN/CLOSED/MERGED
API status cannot be confirmed; ancestry is not proof of an open PR. No GitHub
or Railway connector is callable here. PR #7's missing pull ref is an access/
availability finding, not proof the PR does not exist.

## Defects addressed

* High: PR #5's 106-bar contiguous EMA warmup cannot fit in one 78-bar regular
  session. NDXP now accepts only schedule-verified overnight/weekend boundaries
  while rejecting missing intraday bars, skipped sessions, and misaligned bars.
* High: A caller's fresh `session_open=true` could admit holiday or early-close
  trading. NDXP now independently checks a pinned calendar and rejects closed
  sessions. Open positions remain unresolved when exit data/session is missing.
* High: PR #3 could accept a PR #5 ledger because both used version 1. SPXW
  now has an engine tag and rejects NDXP ledgers (legacy untagged SPX files
  remain supported). NDXP already rejects SPX ledgers.
* Medium: Malformed/unhashable IDs and metadata could crash snapshot processing.
  Both paper engines now reject them before selection.
* Medium: PR #6 accounting did not reconcile per-day P&L or position identity.
  Accounting now independently checks both, and replay fingerprints the calendar
  integration source and pinned calendar package version.
* Pipeline exits must not wait for fresh entry candles. An open position can
  consume exit quotes without indicator history; missing quotes retain the
  position and cash and produce UNRESOLVED rather than a fabricated liquidation.

## Calendar and data limits

`exchange-calendars==4.13.1` provides XNAS as an XNYS regular-equity-session
alias. Tests verify July 3, 2026 closure, November 27 early close, weekends,
and daylight-saving transitions. This is a third-party schedule, not a live
exchange attestation. The official Nasdaq holiday page returned proxy 403;
independent official verification and exceptional closure handling remain
pre-deployment requirements. It is not an SPXW overnight calendar. PR #3 still
requires a trustworthy external overnight-session assertion for that separate
workflow. MT4 compilation was unavailable and is outside the Python pipeline.

No Robinhood Trading MCP tools are exposed, including get_equity_historicals,
get_option_chains, get_option_instruments, or get_option_quotes. No market-data
files or broker/feed bindings were found. Actual three completed QQQ sessions
and actual NDXP bid/ask data were NOT obtained. No orders were accessed. The
new importer is for normalized read-only exports; it does not pretend that an
unverified MCP response schema or authenticated transport has been installed.

## Input and use

`paper_pipeline.py` accepts a JSON bundle:

* `version: 1`, `observed_at` (timezone-aware actual data observation time),
  `source: {kind: "observed", name: "provider/export identity"}`.
* `candles`: ordered QQQ five-minute bars with `symbol`, `timeframe_seconds: 300`,
  timezone-aware `close_time`, `closed: true`, `open`, `high`, `low`, `close`,
  `volume`. A provider's bar-start timestamp must be explicitly converted to
  bar-close time using its documented interval. Never relabel it as an actual
  exchange timestamp. Keep original timestamps/fields as extra row metadata.
* At least three full completed regular sessions and completed current-session
  bars through the most recent five-minute close. No interpolation/forward fill.
* `options` uses the chains/instruments/quotes fields documented in
  SPXW_PAPER.md, with `NDXP` and PM settlement. Quotes retain instrument ID,
  `updated_at`, bid/ask prices, sizes, delta and any extra provider metadata.
  Do not strip fields, invent missing sizes, or replace stale timestamps.
  `complete: true` is only appropriate after the exporting client finishes
  pagination for its declared contract universe and associated quote requests.
  An incomplete or missing universe must use false and cannot open a position.
* No credentials, OAuth state, account secrets, or order history in exports.
  Additional fields inside candle/option rows survive unchanged in the archive.

From the checkout with `.venv` active:

```bash
export TRADING_MODE=paper ROBINHOOD_LIVE_ORDERS=false ALLOW_0DTE=false
python paper_pipeline.py observed-bundle.json --archive /workspace/ndxp-state/archive.json --init
python paper_pipeline.py next-observed-bundle.json --archive /workspace/ndxp-state/archive.json
python paper_replay.py /workspace/ndxp-state/archive.json
```

Only the first invocation uses `--init`. Do not reset existing archives or mix
this runner with a separate ledger. Forward bundles must be <=60 seconds old;
`--historical` explicitly selects offline replay at the original observation
timestamp. The runner uses locking, atomic replacement and fsync. Archive
snapshots are the persisted source of state; replay reconstructs cash and position.
Changing source code/calendar version invalidates existing fingerprints: retain
the original code/dependencies to replay existing archives; do not recompute the
fingerprint to bypass validation or start a new experiment around an open position.

## Validation and review gates

All 96 Python tests passed with paper mode and live orders disabled. Dependency
check and whitespace check passed. One pre-existing non-failing ResourceWarning
remains in test_research_watchlist.py. MT4 and real provider integration are unrun.

`/workspace/paper-review-artifacts` contains explicitly SYNTHETIC regression
bundles, results, accounting and a persisted archive: 3 completed historical
sessions plus current-session bars, one hypothetical quote-model NDXP entry and
stop exit, $122 modeled entry cost, $78 modeled exit value, -$44 modeled P&L,
and $2956 reconciled simulated cash. These prices are test fixtures, NOT market
observations or fills. Fixture use requires both `--historical --allow-fixtures`;
fixture/observed source mixing and resets are rejected. No real-data completed
trade, strategy performance, or production readiness is claimed.

Before deployment: obtain/review #7; confirm PR API merge states; verify the
official calendar; supply actual read-only candle/option exports; run one
signal-qualified real-data paper workflow through persisted entry/exit/replay.
If no signal or usable exit occurs, record NO_TRADE/UNRESOLVED and wait for data,
never force a completion. Review the combined branch and patch first. Live orders
must remain disabled. Existing Railway heartbeat configuration is unchanged and
does not collect this data or invoke the new pipeline.
