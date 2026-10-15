# NDX Iron Condor Bot

IBKR paper-account connection and NDX metadata discovery are available through
`ibkr_paper_probe.py`. See [IBKR_PAPER_SETUP.md](IBKR_PAPER_SETUP.md) for the local
setup and outstanding execution work. This separate diagnostic never sends orders.

NDX iron condor trading assistant with risk controls, dry-run execution, Robinhood MCP integration, trade journaling, and Telegram alerts.

## Current status

Live mode is requested in the review branch configuration. The read-only startup option has been removed; other modes are rejected. `main.py` no longer runs the paper-data demo or order previews. It reports `LIVE_UNAVAILABLE` because supported process authentication and actual order submission are not implemented. This is not a running live bot. No deployment or production setting change has occurred.

Historical simulation modules and archives remain preserved for research.

Implemented:
- NDX option quote and iron condor data models
- Delta-based short strike selection
- Configurable protective wing width
- Net credit, max profit, max loss, and breakeven calculations
- Per-trade and daily risk controls
- Paper market-data provider
- Robinhood MCP order-preview adapter
- Unit tests for strategy and risk management
- Runtime readiness check in `main.py`

Not enabled yet:
- Live Robinhood order submission
- Live NDX option-chain ingestion
- 0DTE trading
- Autonomous execution

## Safety defaults

The repository ships with:
- `TRADING_MODE=live`
- `ALLOW_0DTE=false`
- `ROBINHOOD_LIVE_ORDERS=true`
- Default per-trade risk, daily realized-loss limit, and total open risk: $75 each
- Maximum one trade per day
- Maximum one open position

Live execution should remain disabled until Robinhood's exact MCP multi-leg options schema is verified and the strategy has passed paper testing.

## Run locally

```bash
python main.py
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Robinhood prerequisites

Robinhood documents support for external-agent trading through its Trading MCP, including options tools. An Agentic/MCP account is required for trades placed by an external agent. Iron condors require the account to be eligible for limited-risk spreads/options Level 3.

## Roadmap

1. Live market-data adapter
2. Expiration selector
3. Liquidity and spread filters
4. Entry-time and event filters
5. Trade journal
6. Telegram alerts
7. Robinhood MCP multi-leg schema verification
8. Paper trading against live quotes
9. Controlled live rollout


## Research context feeds

The bot keeps market-context research separate from strategy P&L.

Current research-only feed:
- **SOXX** — semiconductor ETF options/market context

SOXX is intentionally excluded from NDX/SPX/XSP index performance statistics for now. The bot can journal SOXX context such as implied volatility, skew, option liquidity, volume, and open interest, then test whether those features improve later index-strategy decisions. Robinhood MCP currently exposes an active SOXX option chain, so this research feed can be populated from the same market-data integration.



## Railway automation

The repository includes a fail-closed Railway worker configuration:

- Start command: `python automation_runner.py`
- Paper mode only
- Refuses to start when `ROBINHOOD_LIVE_ORDERS=true`
- Journals a scheduler heartbeat every polling interval
- Uses the configured Eastern-time entry/monitor/exit windows

Important: the Robinhood Trading MCP connection available inside ChatGPT is not automatically inherited by a Railway container. The deployed worker can prove scheduling, restarts, journaling, and safety now, but unattended live market-data collection requires a separately authenticated Robinhood MCP transport/client inside the Railway service. Do not place Robinhood credentials or OAuth secrets in the repository.


### Additional research context

- **META** — mega-cap tech options context for NDX/QQQ regime, IV, skew, volume, open interest, and event-volatility research.
- META remains **context-only** and is excluded from index-strategy performance statistics and live trade targeting.


### Expanded semiconductor research context

The research-only watchlist now also includes:
- **AVGO, AMD, MU, TSM, QCOM** — semiconductor leadership and demand-cycle context.
- **AMAT, LRCX, KLAC** — semiconductor equipment/capex-cycle confirmation.

These symbols remain **context-only**. They are excluded from index-strategy P&L and are not live trade targets. Their purpose is to improve NDX/QQQ regime detection using IV, skew, volume, open interest, and event-volatility features.


## Live execution preparation

Live mode and the live-order configuration flag are enabled in this branch at the user's request. Paper simulation is removed from the default entry point. The broker still has no implemented submission transport, and supported Robinhood authentication is not available inside the bot environment. Startup reports these blockers and exits without sending orders. Existing deployment settings and all archives remain unchanged.

Default per-trade risk, daily realized-loss threshold, and aggregate open-risk limit are $75 each. Environment overrides must be reviewed. These are modeled risk settings, not a guaranteed $75 stop or fee-inclusive loss bound. Fee-inclusive risk, remaining daily budget, durable position reconciliation, verified order schema, and continuous exit handling must be completed before any live order can be executed. Historical experiments retain their own frozen rules and must not be reset or reused as a live ledger.
