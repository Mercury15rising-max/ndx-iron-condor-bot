# EMA 8/13/21 paper entry filters

This is an experimental entry filter for the SPXW paper engine. It does not claim
an edge or change the deployed worker, scheduled ChatGPT test, or live orders.
Baseline remains the default; select an EMA mode explicitly for a separate,
clearly labeled experiment. Keep the selected mode fixed for that experiment.

## Rules

- Three ordinary exponential moving averages: periods 8, 13, 21. This is not the
  Triple Exponential Moving Average (TEMA) formula.
- The Python EMA uses first-close initialization and alpha = 2/(period+1).
- `fast_cross`: 8 crosses above 13 on the latest completed candle and 8 > 13 > 21.
  Bearish is the inverse. Equality on the preceding bar is allowed; equality on
  the current bar is not a cross.
- `triple_cross`: the latest completed candle newly establishes 8 > 13 > 21
  (bullish), or 8 < 13 < 21 (bearish). This does not require all three pairwise
  crossings to occur simultaneously. Continued alignment is not another signal.
- Each pairwise 8/13, 8/21 and 13/21 cross is also available in the signal report.
- Default paper integration uses completed 5-minute closes and at least 106
  contiguous completed candles. Forming/future candles do not affect the signal.
  Duplicate, out-of-order, missing, interpolated, mixed-symbol, mixed-timeframe,
  nonpositive or nonfinite closed data fail closed. Latest completed candle must
  be no older than five minutes. Do not fill gaps to satisfy the warmup.
- Only bullish events allow the current call-debit strategy. Bearish signals are
  recorded, but do not create puts or automatically reverse a position.
- A successfully used symbol/bar-close combination is persisted to prevent
  duplicate entry from that crossover. Exits are evaluated before entry signals;
  missing EMA data never suppresses a valid quote-based stop or time exit.
- The $150 entry limit, fresh option quotes, $300 session loss limit, 30% stop,
  60-minute time exit and paper-only restrictions remain in effect.

## Snapshot integration

Keep all fields from SPXW_PAPER.md. Add `signal_symbol` identifying the exact
source series, and `signal_bars` in chronological order. Each bar needs:

```json
{
  "symbol": "YOUR_VERIFIED_SERIES",
  "timeframe_seconds": 300,
  "close_time": "2026-10-14T07:30:00Z",
  "close": "7800.25",
  "closed": true,
  "interpolated": false
}
```

This is a schema example, not market data. `close_time` is the candle END time;
convert providers that label candle starts. Supply history including the prior
completed bar, never only indicator values calculated from an unfinished candle.
Use the same source/history convention across observations: EMA initialization
depends on history. Store source series and timestamps in the paper audit.

For a new EMA experiment with a verified snapshot:

```bash
python spxw_paper.py snapshot.json --state data/spxw_ema_state.json --init --entry-signal triple_cross
```

Subsequent observations use the same command without `--init`. Choose
`--entry-signal fast_cross` to test the fast/middle crossover instead. Do not
create separate ledgers to bypass risk limits on an existing experiment.
The engine API supports `step(state, snapshot, now, entry_signal="triple_cross")`.

An overnight signal needs a verified series that actually updates overnight.
Do not treat the last cash SPX value as a live overnight trend. A futures series
or broker CFD is a proxy with different prices/hours, not SPX itself; identify
the actual symbol explicitly and assess that basis separately. No alternate
feed, credentials, or transport is installed by this change.

## MT4 chart indicator

`mt4/EMA81321.mq4` is a generic source indicator using MetaTrader's native
`iMA(..., MODE_EMA, PRICE_CLOSE, shift)`. It plots the three EMAs and closed-bar
arrows. `TripleAlignmentCross=true` selects triple alignment transitions; false
selects 8/13 crosses filtered by 21. It uses the current chart's symbol/timeframe;
choose M5 to compare the Python defaults. It never sends orders.

Copy the source to MT4's MQL4/Indicators folder, compile in MetaEditor, then attach
to a chart. No MetaEditor/compiler is available in this development environment,
so compilation and visual validation remain outstanding. Compare outputs against
the same data/history before relying on parity: MT4 native initialization and
broker price feeds can differ from the Python first-close seed. The warmup reduces
seed influence but does not prove exact agreement. Closed-bar signals avoid
in-progress-bar fluctuations; later feed history corrections can still change them.

This is not a reproduction of an unspecified third-party "EMA crossover" MT4
indicator. Exact matching requires its source or explicit rules/settings.

Primary references:
- https://docs.mql4.com/indicators/ima
- https://docs.mql4.com/constants/indicatorconstants/enum_ma_method
- https://www.metatrader4.com/en/trading-platform/help/analytics/tech_indicators/moving_average

## Validation

Run `python -m unittest discover -s tests`. Tests cover known EMA arithmetic,
crossing equality boundaries, bullish/bearish/neutral signals, persistent trends,
future/forming candles, bad feed data, warmup/freshness, paper integration,
duplicate signal suppression, and exits without EMA data. These are synthetic
test results, not a backtest or profitability estimate.

## VWAP flip and 9 EMA rollback

Two additional opt-in Python entry modes are `--entry-signal vwap_flip` and
`--entry-signal ema9_rollback`. Both use the same 5-minute closed-candle validation,
106-bar warmup, bullish-only call entries, duplicate-bar guard and independent
spread exits. These are mechanical experimental definitions, not validated edges.

VWAP flip means the previous close was at/below its contemporaneous session VWAP
and the latest close is above its session VWAP (inverse for bearish). VWAP uses
cumulative `(high + low + close) / 3 * volume` divided by cumulative volume.
The snapshot must include `signal_session_start`, a timezone-aware session START
chosen by the feed adapter; there is no guessed midnight reset. Candles from that
anchor must be complete at 5-minute intervals, beginning at anchor + 5 minutes,
with at least two session candles. Each needs positive finite `high`, `low`,
`volume`, and `volume_type: "trade"`. Tick volume is rejected, not substituted.
An overnight-updating traded proxy must be identified explicitly; cash SPX does
not supply a suitable overnight traded-volume series.

“9 EMA rollback” is interpreted as a same-bar pullback/reclaim: prior close above
prior EMA9, latest low touching/below latest EMA9 and close above it, EMA9 rising
and above EMA21. Bearish reverses all comparisons using the high. It does not
require a prior candle close below EMA9 or a subsequent confirmation candle.
High/low are required. Closed-bar OHLC cannot establish intrabar event ordering.
This definition should be reviewed against any intended third-party indicator.

These additions are Python paper-engine signals. The supplied MT4 indicator
remains the 8/13/21 crossover indicator; it does not implement VWAP or rollback.
