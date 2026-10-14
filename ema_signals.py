"""Closed-candle EMA research signals. No execution or market-data access."""
from datetime import datetime
from math import isfinite


def stamp(value):
    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Timezone-aware candle timestamps required")
    return value


def ema(values, period):
    """First-close seed and alpha=2/(period+1); chronological input."""
    if period < 1 or not values:
        raise ValueError("Positive period and nonempty prices required")
    result = [float(values[0])]
    alpha = 2 / (period + 1)
    for value in values[1:]:
        result.append(alpha * float(value) + (1 - alpha) * result[-1])
    return result


def crossover(previous_fast, previous_slow, fast, slow):
    if previous_fast <= previous_slow and fast > slow:
        return "bullish"
    if previous_fast >= previous_slow and fast < slow:
        return "bearish"
    return "none"


def evaluate_ema(bars, now, *, symbol, timeframe_seconds=300):
    """Use only closed candles; reject gaps, mixed feeds and stale signals.

    106 closed candles allow 105 warmup observations plus a comparison bar.
    Warmup mitigates but does not eliminate dependence on the chosen history seed.
    """
    unavailable = {"ready": False, "fast_cross": "none", "triple_cross": "none"}
    try:
        if now.tzinfo is None or not symbol or timeframe_seconds <= 0:
            raise ValueError("Invalid observation time or series configuration")
        closed = []
        previous = None
        for bar in bars:
            end = stamp(bar["close_time"])
            if previous is not None and end <= previous:
                raise ValueError("Duplicate or unordered candles")
            previous = end
            if bar.get("closed") is not True or end > now:
                continue
            if bar["symbol"] != symbol or bar["timeframe_seconds"] != timeframe_seconds:
                raise ValueError("Mixed symbol or timeframe")
            price = float(bar["close"])
            if not isfinite(price) or price <= 0 or bar.get("interpolated") is True:
                raise ValueError("Invalid or interpolated close")
            if closed and (end - closed[-1][0]).total_seconds() != timeframe_seconds:
                raise ValueError("Candle gap; do not forward-fill")
            closed.append((end, price))
        if len(closed) < 106:
            raise ValueError("At least 106 completed candles required")
        if not 0 <= (now - closed[-1][0]).total_seconds() <= timeframe_seconds:
            raise ValueError("Latest completed candle is stale")
        curves = {p: ema([c[1] for c in closed], p) for p in (8, 13, 21)}
        current = {p: curves[p][-1] for p in curves}
        prior = {p: curves[p][-2] for p in curves}
        pairs = {f"{a}/{b}": crossover(prior[a], prior[b], current[a], current[b])
                 for a, b in ((8, 13), (8, 21), (13, 21))}

        def alignment(values):
            if values[8] > values[13] > values[21]:
                return "bullish"
            if values[8] < values[13] < values[21]:
                return "bearish"
            return "neutral"

        trend = alignment(current)
        triple = trend if trend != "neutral" and trend != alignment(prior) else "none"
        fast = pairs["8/13"] if pairs["8/13"] == trend else "none"
        return {"ready": True, "symbol": symbol, "timeframe_seconds": timeframe_seconds,
                "bar_close": closed[-1][0].isoformat(),
                "ema8": current[8], "ema13": current[13], "ema21": current[21],
                "pair_crosses": pairs, "alignment": trend,
                "fast_cross": fast, "triple_cross": triple,
                "seed": "first_close", "closed_bars": len(closed)}
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as error:
        return {**unavailable, "reason": str(error)}


def evaluate_setup(bars, now, *, symbol, mode, session_start=None):
    """Explicit session VWAP flip or same-bar 9 EMA pullback/reclaim."""
    result = evaluate_ema(bars, now, symbol=symbol)
    result.update(vwap_flip="none", ema9_rollback="none")
    if not result["ready"]:
        return result
    try:
        closed = [b for b in bars if b.get("closed") is True and stamp(b["close_time"]) <= now]
        prices = [float(b["close"]) for b in closed]
        curve = ema(prices, 9)
        result["ema9"] = curve[-1]
        if mode == "ema9_rollback":
            last = closed[-1]
            low, high = float(last["low"]), float(last["high"])
            if not all(isfinite(v) and v > 0 for v in (low, high)) or not low <= prices[-1] <= high:
                raise ValueError("Valid high/low required for rollback")
            if prices[-2] > curve[-2] and low <= curve[-1] < prices[-1] and curve[-1] > curve[-2] and curve[-1] > result["ema21"]:
                result[mode] = "bullish"
            elif prices[-2] < curve[-2] and high >= curve[-1] > prices[-1] and curve[-1] < curve[-2] and curve[-1] < result["ema21"]:
                result[mode] = "bearish"
        elif mode == "vwap_flip":
            start = stamp(session_start)
            session = [b for b in closed if stamp(b["close_time"]) > start]
            if len(session) < 2 or (stamp(session[0]["close_time"]) - start).total_seconds() != 300:
                raise ValueError("Complete session history from explicit anchor required")
            numerator = denominator = 0.0
            values = []
            for bar in session:
                high, low, close, volume = (float(bar[k]) for k in ("high", "low", "close", "volume"))
                if not all(isfinite(v) and v > 0 for v in (high, low, close, volume)) or not low <= close <= high:
                    raise ValueError("Positive valid OHLC/volume required for VWAP")
                if bar.get("volume_type") != "trade":
                    raise ValueError("VWAP requires trade volume; tick volume is not accepted")
                numerator += (high + low + close) / 3 * volume
                denominator += volume
                values.append(numerator / denominator)
            result.update(vwap=values[-1], previous_vwap=values[-2], session_start=start.isoformat())
            result[mode] = crossover(float(session[-2]["close"]), values[-2], float(session[-1]["close"]), values[-1])
        else:
            raise ValueError("Unknown setup")
        return result
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as error:
        return {**result, "ready": False, "vwap_flip": "none", "ema9_rollback": "none", "reason": str(error)}
