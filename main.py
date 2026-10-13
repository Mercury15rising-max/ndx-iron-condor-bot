from datetime import date, timedelta

from broker_robinhood_mcp import RobinhoodMCPBroker
from config import SETTINGS
from paper_market_data import PaperMarketDataProvider
from risk_manager import evaluate_trade
from strategy import build_iron_condor


def next_expiration() -> date:
    """Simple paper-mode expiration placeholder.

    Live mode will replace this with an expiration selector from the market-data source.
    """
    return date.today() + timedelta(days=4)


def main() -> None:
    provider = PaperMarketDataProvider()
    broker = RobinhoodMCPBroker(
        live_orders_enabled=SETTINGS.robinhood_live_orders
        and SETTINGS.trading_mode.lower() == "live"
    )

    expiration = next_expiration()
    chain = provider.get_option_chain(SETTINGS.symbol, expiration)

    condor = build_iron_condor(
        chain,
        short_delta_min=SETTINGS.short_delta_min,
        short_delta_max=SETTINGS.short_delta_max,
        wing_width=SETTINGS.wing_width,
    )

    decision = evaluate_trade(
        condor,
        max_risk_per_trade=SETTINGS.max_risk_per_trade,
        daily_realized_pnl=0.0,
        max_daily_loss=SETTINGS.max_daily_loss,
        open_positions=0,
        max_open_positions=SETTINGS.max_open_positions,
        trades_today=0,
        max_trades_per_day=SETTINGS.max_trades_per_day,
    )

    print("NDX Iron Condor Bot")
    print(f"symbol={SETTINGS.symbol}")
    print(f"trading_mode={SETTINGS.trading_mode}")
    print(f"expiration={condor.expiration}")
    print(
        "legs="
        f"{condor.long_put.strike}P / "
        f"{condor.short_put.strike}P / "
        f"{condor.short_call.strike}C / "
        f"{condor.long_call.strike}C"
    )
    print(f"net_credit={condor.net_credit:.2f}")
    print(f"max_profit=${condor.max_profit:.2f}")
    print(f"max_loss=${condor.max_loss:.2f}")
    print(
        f"breakevens={condor.lower_breakeven:.2f} to "
        f"{condor.upper_breakeven:.2f}"
    )
    print(f"risk_approved={decision.approved}")
    print(f"risk_reason={decision.reason}")

    if decision.approved:
        preview = broker.preview_order(condor)
        print("order_preview=")
        print(preview)
    else:
        print("No order preview generated because the risk engine rejected the trade.")


if __name__ == "__main__":
    main()
