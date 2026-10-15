import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    trading_mode: str = os.getenv("TRADING_MODE", "live")
    symbol: str = os.getenv("SYMBOL", "NDX")
    chain_symbol: str = os.getenv("CHAIN_SYMBOL", "NDXP")
    max_trades_per_day: int = int(os.getenv("MAX_TRADES_PER_DAY", "1"))
    max_open_positions: int = int(os.getenv("MAX_OPEN_POSITIONS", "1"))
    max_risk_per_trade: float = float(os.getenv("MAX_RISK_PER_TRADE", "75"))
    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "75"))
    short_delta_min: float = float(os.getenv("SHORT_DELTA_MIN", "0.10"))
    short_delta_max: float = float(os.getenv("SHORT_DELTA_MAX", "0.15"))
    wing_width: float = float(os.getenv("WING_WIDTH", "25"))
    max_bid_ask_width: float = float(os.getenv("MAX_BID_ASK_WIDTH", "2.50"))
    min_bid: float = float(os.getenv("MIN_BID", "0.10"))
    profit_target_pct: float = float(os.getenv("PROFIT_TARGET_PCT", "50"))
    stop_loss_multiple: float = float(os.getenv("STOP_LOSS_MULTIPLE", "2.0"))
    allow_0dte: bool = os.getenv("ALLOW_0DTE", "false").lower() == "true"
    robinhood_live_orders: bool = os.getenv("ROBINHOOD_LIVE_ORDERS", "true").lower() == "true"
    max_quote_age_seconds: int = int(os.getenv("MAX_QUOTE_AGE_SECONDS", "30"))
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2"))
    enable_spxw_0dte_paper: bool = os.getenv("ENABLE_SPXW_0DTE_PAPER", "false").lower() == "true"
    market_timezone: str = os.getenv("MARKET_TIMEZONE", "America/New_York")
    normal_entry_start: str = os.getenv("NORMAL_ENTRY_START", "10:00")
    normal_entry_end: str = os.getenv("NORMAL_ENTRY_END", "14:30")
    zero_dte_entry_start: str = os.getenv("ZERO_DTE_ENTRY_START", "10:00")
    zero_dte_entry_end: str = os.getenv("ZERO_DTE_ENTRY_END", "13:30")
    exit_only_start: str = os.getenv("EXIT_ONLY_START", "15:30")
    max_bid_ask_pct: float = float(os.getenv("MAX_BID_ASK_PCT", "0.20"))
    min_open_interest: int = int(os.getenv("MIN_OPEN_INTEREST", "50"))
    min_option_volume: int = int(os.getenv("MIN_OPTION_VOLUME", "10"))
    min_return_on_risk: float = float(os.getenv("MIN_RETURN_ON_RISK", "0.10"))
    min_credit_to_width: float = float(os.getenv("MIN_CREDIT_TO_WIDTH", "0.10"))
    max_total_open_risk: float = float(os.getenv("MAX_TOTAL_OPEN_RISK", "75"))
    max_positions_per_family: int = int(os.getenv("MAX_POSITIONS_PER_FAMILY", "1"))
    loss_cooldown_minutes: int = int(os.getenv("LOSS_COOLDOWN_MINUTES", "60"))
    event_block_before_minutes: int = int(os.getenv("EVENT_BLOCK_BEFORE_MINUTES", "45"))
    event_block_after_minutes: int = int(os.getenv("EVENT_BLOCK_AFTER_MINUTES", "30"))


SETTINGS = Settings()

