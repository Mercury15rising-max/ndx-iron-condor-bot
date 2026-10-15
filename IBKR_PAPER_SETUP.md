# IBKR paper integration: connection and NDX discovery

This is a separate, non-trading diagnostic for the brokerage-linked IBKR paper
account. It does not change the Robinhood configuration, deployed service,
historical strategy rules, archives, or ledgers. No paper or real orders are sent.
The legacy `main.py` and Railway OAuth service are not the IBKR entry point.

## What is implemented

- Official TWS API `EClient`/`EWrapper` integration, with an optional SDK import.
- Local loopback connection to TWS paper port 7497 or IB Gateway paper port 4002.
- Handshake plus managed-account verification before requesting index metadata.
  Exactly one account must match `IBKR_EXPECTED_PAPER_ACCOUNT`. It must have the
  `DU` paper-account format. A port or prefix alone does not qualify a session.
- NDX `IND`/USD contract qualification, rejecting missing or ambiguous results.
- Complete `reqSecDefOptParams` response collection for the qualified underlying.
- Bounded waits, disconnect cleanup, no credential input, masked/omitted account
  identifiers in reports, and rejection of existing output filenames.
- Place/cancel/global-cancel/exercise methods are blocked in the diagnostic.

`PAPER_CONNECTION_OK` means only that the paper account, NDX underlying and
option-chain metadata were received. It does not prove market-data subscriptions,
an open exchange session, valid individual contracts, fresh quotes, eligibility
for a strategy, or simulated execution. Expirations and strikes are chain metadata;
not every expiry/strike combination necessarily describes an actual contract.

`observed_at` is the time the diagnostic report was produced. It is never a market
quote timestamp. The current probe does not fetch quotes or Greeks or invent fills.

## Setup on the computer running TWS or IB Gateway

1. Install Trader Workstation or IB Gateway from IBKR. Sign in yourself using your
   separate paper credentials. Check that the session says Paper/Simulated Trading.
   No credentials should be entered in the repository, this chat, or Railway.
2. Install the official TWS API SDK from IBKR's download page. Follow its current
   Mac/Linux Python instructions in an isolated Python environment. Use IBKR's
   downloaded `source/pythonclient` package, not an unofficial network PyPI copy.
   For a user-owned extracted SDK directory, the supported local installation is
   `python -m pip install /absolute/path/to/IBJts/source/pythonclient`.
   The package is optional and is not added to the bot's existing requirements.
3. In TWS API Settings, enable socket clients and confirm the paper socket port.
   Keep the API read-only setting enabled for this connection/discovery check.
   This is an IBKR diagnostic control, independent of the legacy bot startup mode.
4. Copy the names in `ibkr-paper.env.example` into your local environment, and
   provide the exact paper account ID shown by IBKR (not the username). For example:

   ```bash
   export IBKR_MODE=paper
   export IBKR_EXPECTED_PAPER_ACCOUNT=DU_REPLACE_WITH_YOUR_PAPER_ACCOUNT_ID
   export IBKR_HOST=127.0.0.1
   export IBKR_PORT=7497
   export IBKR_CLIENT_ID=71
   ```

5. From the repository directory, run the diagnostic. Choose a new report name:

   ```bash
   python ibkr_paper_probe.py --output ibkr-paper-connection-001.json
   ```

   Exit code 0 means `PAPER_CONNECTION_OK`; code 2 means unavailable/configuration
   failure. This command never starts `main.py`, a scheduler, or a trading engine.
   Existing report files are not overwritten; reports are not position ledgers.

The local diagnostic cannot reach your Mac's TWS from a cloud workspace using
127.0.0.1. Run it on the same computer as TWS/Gateway. No public API socket or
remote username/password login has been set up. IBKR application sign-in and
periodic reauthentication remain user steps. This chat has no IBKR account connector.

## Next stages before simulated orders

1. Verify actual account access and NDX/NDXP option permissions on the user's host.
2. Resolve real option contract IDs and request fresh bid/ask/sizes and Greeks;
   preserve source timestamps, label delayed/frozen data, and verify exchange
   session/holiday eligibility. An observed timestamp cannot replace quote age.
3. Connect deterministic iron-condor and butterfly analysis to those snapshots.
4. Enforce $75 per-trade, daily-loss and aggregate-risk limits including quantities,
   fees, existing exposure and remaining daily budget. The report's planned $75
   limits are not claims that this execution integration already exists.
5. Reconcile actual paper positions and pending orders into a separate durable
   ledger. Never reset or reuse historical archives to bypass unresolved state.
6. Implement paper combo orders, idempotency, fill/reject handling, reconciliation,
   and position monitoring/exits. Verify simulator behavior; it differs from live.

No live-money IBKR execution is included or authorized by this paper integration.

## Validation

The new tests use offline synthetic accounts/contracts and SDK test doubles:

```bash
python -m unittest discover -s tests -p 'test_ibkr_paper_probe.py' -v
```

The historical regression suite requires its original frozen fixture limits.
These process-local overrides do not change defaults, deployment variables or archives:

```bash
MAX_RISK_PER_TRADE=500 MAX_DAILY_LOSS=750 MAX_TOTAL_OPEN_RISK=750 \
  python -m unittest discover -s tests -q
```

New $75 risk-default tests separately clear the historical overrides in a subprocess.
Mocked tests do not demonstrate actual IBKR login, a working installed SDK/TWS pair,
data subscriptions or order execution. Those host-dependent checks remain outstanding.

## Official references

- TWS API overview: https://www.interactivebrokers.com/docs/tws-api/doc/introduction
- Mac/Linux SDK installation: https://www.interactivebrokers.com/docs/tws-api/doc/download-the-tws-api/install-the-tws-api-on-mac-os-linux
- SDK downloads: https://download2.interactivebrokers.com/installers/tws-api/index.html
- TWS API configuration: https://www.interactivebrokers.com/campus/trading-lessons/installing-configuring-tws-for-the-api/
- Managed accounts: https://interactivebrokers.github.io/tws-api/managed_accounts.html
- Option-chain API: https://interactivebrokers.github.io/tws-api/options.html
- Paper simulation limitations: https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/
