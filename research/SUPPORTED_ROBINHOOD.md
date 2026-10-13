# Robinhood supported-session workflow

Robinhood Support case 022166665 confirms custom hosted OAuth callbacks are
unsupported. Use the Robinhood connection exposed by a supported AI platform.
Do not transfer its credentials to Railway or retry custom-client registration.

In a supported session, request read-only accounts, option chains, instruments,
and quotes using the platform tools. Check current account eligibility and options
approval. Save only market-data results for research, never credentials or account IDs.
Create contracts.json with instrument_id, symbol, expiration (YYYY-MM-DD),
option_type (put/call), numeric strike and explicitly verified multiplier 100.
Export the structured get_option_quotes result to quotes.json.

    python research/supported_session.py contracts.json quotes.json snapshot.json
    python research/paper_strategy_lab.py snapshot.json --journal research-results.jsonl

The adapter joins by contract UUID, rejects incomplete/mismatched data and keeps
original quote timestamps. The analyzer checks freshness against capture time,
so stale or after-hours data cannot become fresh entry candidates through import.
It reports hypothetical candidates, not fills or profitability.

The condor/butterfly lab still has its own $5 experimental risk ceiling; it is
NOT the $3000 account's small-account gate ($5 per trade, $10 daily). Neither
research module authorizes live orders. Reconcile all risk gates before any live
workflow. The user's stated capital is a planning value, not verified buying power.

No scheduler or autonomous trading is supplied by this session workflow. The
Railway OAuth app is not modified by this branch. Any future trade needs a separate
explicit user instruction and the supported platform's actual trading capabilities.
 

Risk policy update: Both paper modules use research_risk_policy.py ($3000 starting balance, $5 per-trade and $10 daily ceilings). The snapshot lab reports limits but does not track cumulative daily losses or open positions; account_state_checked remains false. It must not authorize execution. Four-leg round-trip assumed fees alone are $8, so no such candidate can meet the $5 ceiling with default fees. Earlier comparisons are historical experiment results, not current approvals.
