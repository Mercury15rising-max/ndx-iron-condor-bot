# Paper strategy lab

Offline, one-snapshot candidate comparison; no orders, assumed fills, scheduled collection, or proven profitability. Does not replace production strategy modules.

Run from this directory:

```sh
python -m unittest -v test_paper_strategy_lab.py
python paper_strategy_lab.py snapshot.json --journal research.jsonl
```

Input JSON: `{"as_of":"2026-10-13T16:00:00+00:00","quotes":[...]}`. Every quote requires symbol, expiration (YYYY-MM-DD), strike, option_type (put/call), bid, ask, delta, quote_timestamp (timezone required), open_interest, volume. Multiplier defaults to 100; other multipliers are rejected. Supply numeric JSON fields, not strings. as_of is the historical evaluation time: never retimestamp old quotes as new.

Compares supplied 1-DTE, 7–14-DTE and 30–45-DTE expirations with exact 25/50/100-point wings. Condor short deltas: absolute 0.10–0.15. Iron butterfly: same-strike call/put, both absolute delta 0.40–0.60. Missing contracts are logged, never synthesized. Research candidates rank by estimated profit/risk; that is not expected return or a profitability forecast.

Fixed research limits: $5 maximum risk; 30-second quote age; minimum OI 50 and volume 10 per leg; spread <=2.50 points and <=20% midpoint; positive credit with >=10% credit/width and return/risk. Entry window weekdays 10:00–14:30 Eastern, end exclusive. This simplified window does not implement holidays, early closes, event checks, portfolio limits or production eligibility. These remain required before any execution integration.

Entry assumptions sell at bid and buy at ask, plus 0.10 points adverse slippage per leg; $1 assumed fee per contract per side (8 fees reserved). These are research assumptions, not verified broker fees or guaranteed package fills. Midpoint is comparison only. Reject midpoint credit >= maximum payoff. All records remain unfilled.

The October 13 19:05 UTC eight-contract snapshot was replayed locally: 15 combinations, 2 fully priced rejections, 13 missing-wing records, 0 candidates/fills. No longer-dated quotes were supplied; those comparisons are not yet empirically tested. No position lifecycle, realized P&L, exit slippage simulation or profitability backtest is implemented. Local live market snapshots are not included in this repository.
 

Risk policy update: Both paper modules use research_risk_policy.py ($3000 starting balance, $5 per-trade and $10 daily ceilings). The snapshot lab reports limits but does not track cumulative daily losses or open positions; account_state_checked remains false. It must not authorize execution. Four-leg round-trip assumed fees alone are $8, so no such candidate can meet the $5 ceiling with default fees. Earlier comparisons are historical experiment results, not current approvals.
