"""Report requested runtime configuration without submitting any orders."""
from config import SETTINGS


def main() -> None:
    mode = SETTINGS.trading_mode.lower()
    if mode not in ("live", "read_only"):
        raise SystemExit("Paper startup removed. Use live or read_only mode.")
    if mode == "read_only" and SETTINGS.robinhood_live_orders:
        raise SystemExit("Read-only mode conflicts with live orders enabled.")
    if mode == "live" and not SETTINGS.robinhood_live_orders:
        raise SystemExit("Live mode requires ROBINHOOD_LIVE_ORDERS=true.")
    print(f"NDX Iron Condor Bot: requested mode={mode}")
    print(f"live_orders_configured={SETTINGS.robinhood_live_orders}")
    print("Paper trading is not run by this entry point.")
    print("Robinhood authentication is unverified by this process.")
    if mode == "live":
        raise SystemExit("LIVE_UNAVAILABLE: supported authenticated MCP transport and "
                         "implemented order submission are required; no order sent.")


if __name__ == "__main__":
    main()
