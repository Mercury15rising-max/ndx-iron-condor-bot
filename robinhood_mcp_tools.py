"""Robinhood Trading MCP integration contract.

Public Robinhood documentation currently exposes these external-agent options tools:
- get_option_chains
- get_option_instruments
- get_option_quotes
- review_option_order
- place_option_order

This module deliberately defines only the bot-side protocol. The exact MCP transport
and response schema are injected at runtime after the Robinhood connection is available.
"""

from datetime import date
from typing import Any, Protocol


class RobinhoodTradingMCP(Protocol):
    def get_option_chains(self, symbol: str) -> dict[str, Any]:
        ...

    def get_option_instruments(
        self,
        symbol: str,
        expiration: date,
        option_type: str | None = None,
    ) -> list[dict[str, Any]]:
        ...

    def get_option_quotes(
        self,
        instrument_ids: list[str],
    ) -> list[dict[str, Any]]:
        ...

    def review_option_order(self, order: dict[str, Any]) -> dict[str, Any]:
        ...

    def place_option_order(self, order: dict[str, Any]) -> dict[str, Any]:
        ...
