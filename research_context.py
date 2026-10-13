from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from paper_journal import PaperJournal, PaperTradeRecord


@dataclass(frozen=True)
class ResearchSnapshot:
    symbol: str
    underlying_price: float | None
    implied_volatility: float | None
    put_call_skew: float | None
    average_bid_ask_width: float | None
    option_volume: int | None
    open_interest: int | None
    metadata: dict[str, Any]


def journal_research_snapshot(
    journal: PaperJournal,
    snapshot: ResearchSnapshot,
) -> None:
    """Persist market-context features without mixing them into strategy P&L."""
    journal.write(
        PaperTradeRecord(
            event="research_snapshot",
            chain_symbol=snapshot.symbol,
            strategy="research_context",
            expiration="",
            score=None,
            max_profit=None,
            max_loss=None,
            reason="Research-only context; excluded from index strategy performance.",
            metadata={
                **asdict(snapshot),
                "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
    )
