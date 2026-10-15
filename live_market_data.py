"""Read-only Robinhood option adapter; incomplete or malformed feeds fail closed."""
from datetime import date
from math import isfinite
from typing import Protocol, Any

from market_data import MarketDataProvider
from models import OptionQuote


class RobinhoodOptionsClient(Protocol):
    def get_option_instruments(
        self, *, chain_symbol: str, expiration_dates: str,
        state: str = "active", cursor: str | None = None,
    ) -> dict[str, Any]:
        ...

    def get_option_quotes(self, *, instrument_ids: list[str]) -> dict[str, Any]:
        ...


def _rows(response, name):
    if not isinstance(response, dict) or not isinstance(response.get("data"), dict):
        raise ValueError("Malformed Robinhood data response")
    data = response["data"]
    rows = data.get(name)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError(f"Malformed Robinhood {name}")
    return data, rows


def _number(value, label):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"Missing or invalid {label}") from error
    if isinstance(value, bool) or not isfinite(result):
        raise ValueError(f"Non-finite or invalid {label}")
    return result


def _optional_count(value, label):
    if value in (None, ""):
        return None
    result = _number(value, label)
    if result < 0 or not result.is_integer():
        raise ValueError(f"Invalid {label}")
    return int(result)


class RobinhoodMarketDataProvider(MarketDataProvider):
    """Collect every contract page and join original quotes by ID.

    Omit the upstream tradability query filter: observed responses can omit
    contracts that are themselves marked tradable. Enforce eligibility locally.
    A missing quote or delta rejects the chain rather than silently changing
    deterministic short-strike ranking. No timestamp is synthesized or refreshed.
    """

    def __init__(self, client: RobinhoodOptionsClient):
        self.client = client

    def get_option_chain(self, symbol: str, expiration: date) -> list[OptionQuote]:
        instruments = []
        seen_ids = set()
        seen_cursors = set()
        cursor = None
        while True:
            request = dict(chain_symbol=symbol, expiration_dates=expiration.isoformat(),
                           state="active")
            if cursor is not None:
                request["cursor"] = cursor
            data, rows = _rows(self.client.get_option_instruments(**request), "instruments")
            for row in rows:
                identifier = row.get("id")
                if not isinstance(identifier, str) or not identifier or identifier in seen_ids:
                    raise ValueError("Missing or duplicate instrument ID")
                seen_ids.add(identifier)
                if (row.get("chain_symbol") != symbol
                        or row.get("expiration_date") != expiration.isoformat()):
                    raise ValueError("Contract symbol/expiration differs from request")
                if row.get("state") != "active" or row.get("tradability") != "tradable":
                    continue
                if row.get("type") not in ("call", "put"):
                    raise ValueError("Invalid option type")
                instruments.append(row)
            cursor = data.get("next")
            if cursor in (None, ""):
                break
            if not isinstance(cursor, str) or cursor in seen_cursors:
                raise ValueError("Invalid or repeated instrument pagination cursor")
            seen_cursors.add(cursor)

        if not instruments:
            return []
        ids = [row["id"] for row in instruments]
        quotes_by_id = {}
        # Bounded requests avoid transport limits; closes are not used for entry.
        for start in range(0, len(ids), 100):
            batch = ids[start:start + 100]
            _, results = _rows(
                self.client.get_option_quotes(instrument_ids=batch), "results"
            )
            for result in results:
                quote = result.get("quote")
                if not isinstance(quote, dict):
                    raise ValueError("Missing or malformed option quote")
                identifier = quote.get("instrument_id")
                if (not isinstance(identifier, str) or identifier not in batch
                        or identifier in quotes_by_id):
                    raise ValueError("Unexpected or duplicate quote ID")
                quotes_by_id[identifier] = quote
            if any(identifier not in quotes_by_id for identifier in batch):
                raise ValueError("Incomplete option quote batch")

        normalized = []
        for instrument in instruments:
            quote = quotes_by_id[instrument["id"]]
            strike = _number(instrument.get("strike_price"), "strike")
            bid = _number(quote.get("bid_price"), "bid")
            ask = _number(quote.get("ask_price"), "ask")
            delta = _number(quote.get("delta"), "delta")
            if strike <= 0 or bid < 0 or ask < bid or abs(delta) > 1:
                raise ValueError("Invalid strike, bid/ask or delta")
            iv = quote.get("implied_volatility")
            iv = None if iv in (None, "") else _number(iv, "implied volatility")
            if iv is not None and iv < 0:
                raise ValueError("Negative implied volatility")
            normalized.append(OptionQuote(
                symbol=symbol, expiration=expiration, strike=strike,
                option_type=instrument["type"], bid=bid, ask=ask, delta=delta,
                implied_volatility=iv,
                open_interest=_optional_count(quote.get("open_interest"), "open interest"),
                volume=_optional_count(quote.get("volume"), "volume"),
                quote_timestamp=quote.get("updated_at"),
            ))
        return normalized

