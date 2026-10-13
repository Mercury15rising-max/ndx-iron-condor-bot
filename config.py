import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    trading_mode: str = os.getenv("TRADING_MODE", "paper")
    symbol: str = os.getenv("SYMBOL", "NDX")
    chain_symbol: str = os.getenv("CHAIN_SYMBOL", "NDXP")
    max_trades_per_day: int = int(os.getenv("MAX_TRADES_PER_DAY", "1"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "1"))
    max_risk_per_trade: float = float(os.getenv("MAX_RISK_PER_TRADE", "500"))
    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "750"))
    short_delta_min: float = float(os.getenv("SHORT_DELTA_MIN", "0.10"))
    short_delta_max: float = float(os.getenv("SHORT_DELTA_MAX", "0.15"))
    wing_width: float = float(os.getenv("WING_WIDTH", "25"))
    max_bid_ask_width: float = float(os.getenv("MAX_BID_ASK_WIDTH", "2.50"))
    min_bid: float = float(os.getenv("MIN_BID", "0.10"))
    profit_target_pct: float = float(os.getenv("PROFIT_TARGET_PCT", "50"))
    stop_loss_multiple: float = float(os.getenv("STOP_LOSS_MULTIPLE", "2.0"))
    allow_0dte: bool = os.getenv("ALLOW_0DTE", "false").lower() == "true"
    robinhood_live_orders: bool = os.getenv("ROBINHOOD_LIVE_ORDERS", "false").lower() == "true"

SETTINGS = Settings()
