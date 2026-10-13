from config import SETTINGS
from broker_robinhood_mcp import RobinhoodMCPBroker

def main() -> None:
    broker = RobinhoodMCPBroker(
        live_orders_enabled=SETTINGS.robinhood_live_orders
        and SETTINGS.trading_mode.lower() == "live"
    )
    print("NDX Iron Condor Bot")
    print(f"symbol={SETTINGS.symbol}")
    print(f"trading_mode={SETTINGS.trading_mode}")
    print(f"live_orders_enabled={broker.live_orders_enabled}")
    print("Status: scaffold ready. Market-data connector is the next milestone.")

if __name__ == "__main__":
    main()
