import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from config import SETTINGS
from market_schedule import evaluate_market_session
from paper_journal import PaperJournal, PaperTradeRecord


POLL_SECONDS = int(os.getenv("POLL_SECONDS", "60"))


def heartbeat(journal: PaperJournal, now: datetime) -> None:
    session = evaluate_market_session(
        now,
        is_zero_dte=False,
        timezone_name=SETTINGS.market_timezone,
        normal_entry_start=SETTINGS.normal_entry_start,
        normal_entry_end=SETTINGS.normal_entry_end,
        zero_dte_entry_start=SETTINGS.zero_dte_entry_start,
        zero_dte_entry_end=SETTINGS.zero_dte_entry_end,
        exit_only_start=SETTINGS.exit_only_start,
    )
    journal.write(
        PaperTradeRecord(
            event="runner_heartbeat",
            chain_symbol="SYSTEM",
            strategy="automation",
            expiration="",
            score=None,
            max_profit=None,
            max_loss=None,
            reason=session.reason,
            metadata={
                "allow_new_entries": session.allow_new_entries,
                "monitor_positions": session.monitor_positions,
                "exit_only": session.exit_only,
                "trading_mode": SETTINGS.trading_mode,
                "live_orders_enabled": SETTINGS.robinhood_live_orders,
            },
        )
    )


def main() -> None:
    if SETTINGS.trading_mode.lower() != "paper":
        raise SystemExit("Automation runner is restricted to paper mode.")
    if SETTINGS.robinhood_live_orders:
        raise SystemExit("Automation runner refuses to start with live orders enabled.")

    journal = PaperJournal()
    tz = ZoneInfo(SETTINGS.market_timezone)
    print("Paper automation runner started.")
    print(f"market_timezone={SETTINGS.market_timezone}")
    print(f"poll_seconds={POLL_SECONDS}")

    while True:
        now = datetime.now(timezone.utc)
        local_now = now.astimezone(tz)

        # For now this runner proves deployment, scheduling, journaling, and
        # fail-closed safety. The live Robinhood MCP transport must be attached
        # before market-data scans can run unattended outside ChatGPT.
        heartbeat(journal, now)
        print(f"heartbeat={local_now.isoformat()}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
