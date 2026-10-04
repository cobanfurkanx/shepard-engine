"""Exchange payload validation and Wilder RSI with explicit warm-up."""

import math
from dataclasses import asdict, dataclass

INTERVAL_MS = 900_000


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_ms: int
    close: float
    quote_volume: float

    def to_dict(self):
        return asdict(self)


def number(value, *, positive=False):
    result = float(value)
    if not math.isfinite(result) or result < 0 or (positive and result == 0):
        raise ValueError("invalid exchange number")
    return result


def parse_event(event: dict, symbols: set[str], now_ms: int):
    data = event.get("data", event)
    symbol = data.get("s")
    if symbol not in symbols:
        return None
    if data.get("e") == "24hrTicker":
        event_ms = int(data["E"])
        if event_ms > now_ms + 5000 or now_ms - event_ms > 60_000:
            return None
        return {"symbol": symbol, "price": number(data["c"], positive=True), "event_ms": event_ms}
    if data.get("e") != "kline":
        return None
    kline = data["k"]
    if kline.get("i") != "15m" or kline.get("x") is not True:
        return None
    opened, closed = int(kline["t"]), int(kline["T"])
    if opened < 0 or opened % INTERVAL_MS or closed != opened + INTERVAL_MS - 1:
        raise ValueError("invalid candle interval")
    if closed >= now_ms:
        return None
    low, high = number(kline["l"], positive=True), number(kline["h"], positive=True)
    opening, close = number(kline["o"], positive=True), number(kline["c"], positive=True)
    if not low <= min(opening, close) <= max(opening, close) <= high:
        raise ValueError("invalid OHLC range")
    return Candle(symbol, opened, close, number(kline["q"]))


def rsi_value(gain: float, loss: float) -> float:
    if loss == 0:
        return 50.0 if gain == 0 else 100.0
    return 100 - 100 / (1 + gain / loss)


def rsi_series(closes: list[float], period: int = 14) -> list[float | None]:
    if period < 1 or any(not math.isfinite(x) or x <= 0 for x in closes):
        raise ValueError("invalid RSI input")
    result: list[float | None] = [None] * min(period, len(closes))
    gain = loss = 0.0
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        up, down = max(change, 0), max(-change, 0)
        if index <= period:
            gain += up / period
            loss += down / period
        else:
            gain = (gain * (period - 1) + up) / period
            loss = (loss * (period - 1) + down) / period
        if index >= period:
            result.append(rsi_value(gain, loss))
    return result
