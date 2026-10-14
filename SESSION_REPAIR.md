# Session-aware signal repair

The prior evaluator demanded 106 consecutive wall-clock 5-minute candles. A US
regular session has only 78 such bars, so a normal session boundary caused failure.
The repair keeps EMA state across real trading bars without adding synthetic bars.

Supply `signal_calendar` in NDX/SPX snapshots and watchlist scans:

    {"complete": true, "source": "your verified exchange-calendar provider/version",
     "coverage_start": "2026-10-12T00:00:00Z",
     "coverage_end": "2026-10-15T00:00:00Z",
     "sessions": [
       {"open": "2026-10-12T13:30:00Z", "close": "2026-10-12T20:00:00Z"},
       {"open": "2026-10-13T13:30:00Z", "close": "2026-10-13T20:00:00Z"},
       {"open": "2026-10-14T13:30:00Z", "close": "2026-10-14T20:00:00Z"}]}

This example illustrates the schema, not a built-in calendar service. The caller
must supply the complete authoritative schedule for coverage, including early
closes/holidays/DST. A source label is provenance, not authentication. Do not
construct the schedule by guessing from missing bars. Missing whole sessions are
rejected when present in the supplied calendar. Incorrect omitted sessions in a
falsely declared complete calendar cannot be detected by this module.

The supplied bars must match all expected candle ends between first and last bar.
Partial history may begin mid-session; warmup still requires at least106 actual
closed bars. Fetch at least three regular sessions for morning evaluation. Missing
intraday/open/close bars, unexpected off-session timestamps, duplicates, mixed
series, interpolation, stale/future latest data and incomplete coverage are not
silently repaired. Without a calendar, legacy strict continuous mode remains.

Robinhood historical bars label interval starts. normalize_robinhood adds five
minutes, excludes forming bars from signals, and preserves source order. VWAP
requires a current-session anchor and cannot accumulate across scheduled closures.
NDX and SPX engines pass the calendar through; exits remain independent of signals.
The replay fingerprint now includes session_bars.py. Old archives require the
original source revision; they are never silently migrated.

Run the watchlist signal check with a JSON object containing `series` (Robinhood
regular 5minute history results), `signal_calendar` and `signal_session_start`:

    python paper_signal_scan.py snapshot.json --observed-at 2026-10-14T11:00:00-04:00

All14 configured assets are evaluated for EMA, rollback and VWAP. Missing symbols
are reported individually. This is signal validation, not a stock trade simulator.
Context-only roles remain unchanged. Stock execution requires a separate reviewed
position-sizing/entry/exit policy; index spread rules cannot simply be reused for
shares or physically settled equity options. No scheduler/feed or deployment is
added. This document supersedes the contiguous wall-clock-history limitation in
EMA_STRATEGY.md and NDX_DETERMINISTIC.md when a valid calendar is supplied.
