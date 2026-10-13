import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperTradeRecord:
    event: str
    chain_symbol: str
    strategy: str
    expiration: str
    score: float | None
    max_profit: float | None
    max_loss: float | None
    reason: str
    metadata: dict[str, Any]


class PaperJournal:
    """Append-only JSONL journal for scans, paper entries, exits, and rejections."""

    def __init__(self, path: str = "data/paper_trades.jsonl"):
        self.path = Path(path)

    def write(self, record: PaperTradeRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(record)
        payload["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True) + "\n")
