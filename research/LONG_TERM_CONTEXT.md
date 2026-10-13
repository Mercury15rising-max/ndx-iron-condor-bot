# Long-term research context

regime_comparison.py now loads market_200_sessions.json by default and appends long_term_research to each journal evaluation. Override with --research-context PATH when refreshed data is available.

The bundled sample ends 2026-10-12 and includes 18 equity/ETF symbols, 200 sessions of descriptive metrics and 199-return correlations. It is accepted only when its end matches the caller's --completed-session. Caller must resolve the actual prior exchange session; this remains an offline snapshot evaluator, not a live freshness service. Stale/missing long-term context is explicitly labeled and does not supply metrics. Existing trend/volatility filter gates are unchanged and independently require valid histories. Long-term context itself does not authorize or reject orders.

The source data's methodology is embedded in the JSON. Nearest peers are ranked by absolute return correlation; negative values indicate opposite historical movement, not guaranteed hedges. No correlations alter sizing. No thresholds were optimized against this sample and no prediction model was trained. Per-trade and daily risk limits, one position/entry limits, costs and quote gates remain unchanged.

NDX/SPX are not present in this equity dataset: their results receive missing context rather than substituted ETF histories. Fresh underlying index histories and option quotes remain necessary for index strategy research. No scheduler, deployment, fills or live trading is added by this change.
