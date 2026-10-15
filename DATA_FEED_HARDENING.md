# Read-only feed and regular-session hardening

These changes address defects reproduced during the October 14 review. They
do not connect a scheduler to the paper engine, deploy the review branch, or
make stale Robinhood overnight prices usable. Future market-data and paper
tests are restricted to regular exchange hours and the strategy entry window.

## Changes

- Collect every option-instrument page, reject duplicate IDs/repeated cursors,
  and fetch quotes in batches of at most 100 contracts.
- Omit the inconsistent upstream tradability filter and check returned active,
  tradable metadata locally. Validate contract symbol and expiration.
- Reject incomplete quote batches, duplicate/unexpected IDs, missing deltas,
  non-finite numbers and malformed books with explicit errors. Do not silently
  drop missing ranking data or manufacture a replacement contract or timestamp.
- Reject crossed/non-finite books and unknown open interest/volume when a
  positive liquidity minimum is configured.
- Reject timezone-naive quote/observation times in the entry safety gate.
- Use the existing pinned regular-session calendar for scheduling. Holidays,
  weekends and early closes block entries; early-close sessions enter the
  exit-only window at least 30 minutes before their actual scheduled close.

## Validation and limits

The original 137 tests pass, along with eight new offline synthetic regression
tests (145 total). The new tests fail on the original code. Dependency and
whitespace checks pass. A pre-existing unclosed-file ResourceWarning remains
in test_research_watchlist.py.

No paper replay engine, fingerprinted implementation source, trading archive,
or production configuration is changed. Existing source fingerprints remain
valid. The calendar is a schedule, not a live exceptional-closure attestation.
Fresh market data, authoritative durable paper state and an integrated
entry/exit scheduler remain necessary for an end-to-end paper test.
