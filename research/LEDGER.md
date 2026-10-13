# Paper account ledger

Run the snapshot analyzer with a persistent SQLite path:

    python research/paper_strategy_lab.py snapshot.json --journal results.jsonl --ledger paper-account.sqlite

The CLI checks each hypothetical candidate against the ledger without creating
fills. Starting simulated capital is $3000; risk is capped at the smaller of
$30 and 1% of current realized balance. Daily loss budget is the smaller of $60
and 2%. One open position and one new simulation per Eastern calendar day.
Losses are accumulated gross of winning trades, using net-of-cost trade P&L;
wins do not erase losses from the daily loss counter. Open risk carries overnight.
Money is stored in integer cents, SQLite writes are transactional, and backdated
events before the latest ledger event are rejected. Keep historical replays in
separate databases. Do not delete a ledger to reset its limits.

A simulation harness may call open_simulation(id, risk, timestamp, evidence) only
after quote/strategy gates pass. It atomically rechecks risk before reserving it.
close_simulation requires explicit cent-precise net P&L and supporting simulation
evidence; it does not derive fills from quotes. Never feed real orders to this API.
The analyzer's check alone is not a reservation. Production gates remain false.

This tracks realized P&L and reserved maximum loss, not intraday mark-to-market
or broker balances. No live orders, scheduler, or deployed service is introduced.
The earlier README/SUPPORTED_ROBINHOOD command examples require --ledger now.
