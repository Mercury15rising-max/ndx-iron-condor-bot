from dataclasses import dataclass
from typing import Literal

ResearchRole = Literal["context_only", "paper_strategy"]


@dataclass(frozen=True)
class ResearchAsset:
    symbol: str
    asset_type: str
    role: ResearchRole
    notes: str


DEFAULT_RESEARCH_WATCHLIST = (
    ResearchAsset(
        symbol="SOXX",
        asset_type="ETF",
        role="context_only",
        notes=(
            "Semiconductor ETF. Track separately from cash-settled index products; "
            "use as a market-context feature until enough paper data exists."
        ),
    ),
)
