# NDX Iron Condor Bot

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
