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
    ResearchAsset(
        symbol="CRDO",
        asset_type="equity",
        role="context_only",
        notes=(
            "High-beta semiconductor/networking equity. Track IV, skew, volume, "
            "open interest, and directional moves as context for NDX/NDXP."
        ),
    ),
    ResearchAsset(
        symbol="SITM",
        asset_type="equity",
        role="context_only",
        notes=(
            "Semiconductor timing equity with a thinner options calendar. Use as "
            "research context only and do not mix with index strategy performance."
        ),
    ),
    ResearchAsset(
        symbol="META",
        asset_type="equity",
        role="context_only",
        notes=(
            "High-value mega-cap tech options context. Track IV, put/call skew, "
            "volume, open interest, and event volatility as context for QQQ/NDX."
        ),
    ),
    ResearchAsset(
        symbol="AVGO",
        asset_type="equity",
        role="context_only",
        notes=(
            "Broadcom mega-cap semiconductor/AI infrastructure context. Track IV, skew, volume, OI, and event volatility for NDX/QQQ regime confirmation."
        ),
    ),
    ResearchAsset(
        symbol="AMD",
        asset_type="equity",
        role="context_only",
        notes=(
            "High-beta semiconductor context. Track IV, skew, volume, OI, and directional moves as a leading risk-on/risk-off input for NDX."
        ),
    ),
    ResearchAsset(
        symbol="MU",
        asset_type="equity",
        role="context_only",
        notes=(
            "Memory-cycle semiconductor context. Track options activity as a demand-cycle and volatility confirmation signal for NDX/QQQ."
        ),
    ),
    ResearchAsset(
        symbol="TSM",
        asset_type="equity",
        role="context_only",
        notes=(
            "Global semiconductor foundry context. Track IV, skew, volume, OI, and event volatility for semiconductor-cycle confirmation."
        ),
    ),
    ResearchAsset(
        symbol="QCOM",
        asset_type="equity",
        role="context_only",
        notes=(
            "Mobile/AI semiconductor demand context. Use options activity as a secondary confirmation signal for tech regime detection."
        ),
    ),
    ResearchAsset(
        symbol="AMAT",
        asset_type="equity",
        role="context_only",
        notes=(
            "Semiconductor equipment/capex context. Track options activity as a fab-investment and cycle confirmation signal."
        ),
    ),
    ResearchAsset(
        symbol="LRCX",
        asset_type="equity",
        role="context_only",
        notes=(
            "Semiconductor equipment context. Track IV, skew, volume, OI, and event volatility as a capex-cycle confirmation input."
        ),
    ),
    ResearchAsset(
        symbol="KLAC",
        asset_type="equity",
        role="context_only",
        notes=(
            "Semiconductor process-control/equipment context. Use options activity as a lower-weight capex-cycle confirmation signal."
        ),
    ),
)
