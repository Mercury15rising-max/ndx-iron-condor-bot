# Watchlist trend research

Run from the repository root:

    python research/trend_features.py histories.json --completed-session 2026-10-12 --database /data/watchlist_trends.sqlite

Uses every symbol in research_watchlist.DEFAULT_RESEARCH_WATCHLIST. Input JSON has
adjustment_type="split", source, and results containing Robinhood daily regular
historical entries (symbol, interval, bounds, bars). Fetch symbols in batches of
at most ten, with at least 220 observed sessions. Credentials are not input data.

Records 50/200-session simple averages, percentage distance of the last completed
bar close from each, and percentage change in SMA200 over 20 observed sessions.
Bullish means above rising SMA200; bearish means below falling SMA200; otherwise
mixed. These descriptive labels are not execution signals.

Caller supplies the last completed exchange session, accounting for holidays.
Unfinished and interpolated bars are excluded; missing latest sessions and short
history yield unknown regimes. Duplicate sessions and invalid closes fail that
symbol without stopping the batch. Historical interior gaps are not calendar
validated: observations are counted, and no missing prices are filled.
Closes are provider bar closes, not official settlement prices. Split adjustments
may revise past data. SQLite stores one snapshot per symbol/requested session;
reruns replace that session, preserving other dates. This is not a revision log.

This CLI is a research component on paper-strategy-lab. It has no scheduler,
broker login, orders, or production scanner wiring. Schedule only after supplying
a working data adapter and exchange calendar. Its data does not prove strategy
profitability. Tests: python -m unittest discover -s research -p test_trend_features.py
