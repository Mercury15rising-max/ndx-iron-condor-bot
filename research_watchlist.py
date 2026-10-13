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
    ResearchAsset(
        symbol="QQQ",
        asset_type="ETF",
        role="context_only",
        notes=(
            "Nasdaq-100 ETF. Use as a liquid Nasdaq context feed for IV, skew, "
            "volume, open interest, and directional confirmation versus NDX/NDXP."
        ),
    ),
    ResearchAsset(
        symbol="SPXL",
        asset_type="ETF",
        role="context_only",
        notes=(
            "3x leveraged S&P 500 ETF. Use only as a higher-sensitivity broad-market "
            "context/stress feed; keep separate from SPX/XSP performance statistics."
        ),
    ),
)
