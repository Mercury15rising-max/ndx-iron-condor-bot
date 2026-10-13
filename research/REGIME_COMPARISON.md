# Shadow regime comparison v1

Run from the research directory:

```
python regime_comparison.py snapshot.json histories.json --completed-session YYYY-MM-DD --ledger paper-account.sqlite --journal regime-results.jsonl
```

The completed session must be the previous exchange session; the caller resolves holidays. History must explicitly declare adjustment_type=split and contain regular daily bars. Exact underlying symbols are required: QQQ is not silently substituted for NDX, nor SPY for SPX. Current-day and interpolated bars are excluded. At least 220 closing observations are needed for the existing 200-day trend classification. Interior missing sessions are not yet exchange-calendar validated.

Each existing cost/quote/account-gated condor or iron butterfly receives four shadow labels: baseline, mixed trend, volatility not expanding, combined. Mixed trend means the existing price-versus-SMA200 and 20-observation SMA200 slope disagree; it does NOT prove a range-bound market. Volatility uses the sample standard deviation of 20 and 60 daily log returns, in percent, without annualization. The volatility experiment passes when RV20 <= RV60. These are unvalidated, predeclared research hypotheses, not tuned profitable rules. Missing/stale history blocks filtered variants. Risk and liquidity rejections remain rejected in every variant.

All variants share one account-gated snapshot; this is not four independently funded portfolios. No fills or reservations occur. Existing $30/trade and $60/day maximum limits remain, with downward balance scaling. One open position and one entry per day remain enforced by the ledger.

The journal records symbol, strategy, context, costs, maximum loss, original rejection reasons and variant decisions. It cannot produce realized profit, win rate or strategy drawdown without subsequent timestamped option marks and an explicit fill/exit model. Do not treat theoretical maximum profit as realized P&L. Compare future net results out of sample before selecting a filter. This module is not scheduled or deployed and does not enable live trading.
