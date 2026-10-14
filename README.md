# NDX Iron Condor Bot

The repository now includes a tested controlled live-order adapter; see
**Controlled live execution adapter** below for its deployment prerequisites.

NDX iron condor trading assistant with risk controls, dry-run execution, Robinhood MCP integration, trade journaling, and Telegram alerts.

## Current status

Version 1 is intentionally **paper-mode first**.

Implemented:
- NDX option quote and iron condor data models
- Delta-based short strike selection
- Configurable protective wing width
- Net credit, max profit, max loss, and breakeven calculations
- Per-trade and daily risk controls
- Paper market-data provider
- Robinhood MCP order-preview adapter
- Unit tests for strategy and risk management
- End-to-end dry-run pipeline in `main.py`

Not enabled yet:
- Live Robinhood order submission
- Live NDX option-chain ingestion
- 0DTE trading
- Autonomous execution

## Safety defaults

The repository ships with:
- `TRADING_MODE=paper`
- `ALLOW_0DTE=false`
- `ROBINHOOD_LIVE_ORDERS=false`
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


## Controlled live execution adapter

`live_execution.py` adds a two-stage iron-condor execution path for an
authenticated `RobinhoodCloudMCP` client. It uses the order schema exposed by
the connected Robinhood Trading plugin: instrument UUIDs, four opening legs,
a positive user-supplied net credit, limit/GFD orders, regular hours, and a
persistent UUID `ref_id`. It does not infer a live price from leg quotes.

The caller supplies the account number, quantity, risk ceiling, a persistent
SQLite journal path, and an async `entry_gate`. That gate must obtain current
broker state and enforce market sessions/holidays, fresh quotes, event blocks,
daily loss/trade limits, and exposure including pending orders. It is checked
at review and again before submission. Do not substitute heartbeat or paper
state for the live gate.

The adapter checks account accessibility, Level 3 permissions, individual
margin/limited-margin status, and active tradable standard index contracts.
It recomputes expiration maximum loss from wing width and the specified net
credit. This calculation excludes fees and execution slippage.

Call `review(...)` first and display the complete payload and broker review,
including alert text verbatim. Only after the user approves that exact review
and acknowledges its alerts may the application call
`submit(ref_id, confirmed=True)`. Tickets expire after 30 seconds.
The stored payload cannot be changed by mutating the returned review.
Account eligibility is checked again before sending.

Each submission attempt is committed to SQLite before the broker call.
After a timeout or uncertain response, do not create another ticket or retry
automatically: reconcile the existing UUID with broker order history first.
A successful response may mean queued or awaiting Robinhood approval; it is
not proof of a fill. The caller must monitor order status, fills, positions,
and exits. Keep the SQLite journal on persistent storage across restarts.

**Deployment status:** This module is tested with simulated MCP responses.
It is not attached to the scheduled worker or cloud web routes. The existing
worker still runs paper heartbeats, and defaults remain paper mode. Enabling
environment flags alone cannot enable live trading. Deployment still requires
verified cloud OAuth, a live entry gate, broker response validation, position
and exit reconciliation, and the exact approved account/order settings.
No live order was reviewed or placed during development.


