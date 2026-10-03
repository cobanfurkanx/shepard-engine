import math

import pytest

from shepard_engine.market import Candle, parse_event, rsi_series


def candle_event(closed=True):
    return {"e": "kline", "s": "BTCUSDT", "k": {
        "t": 0, "T": 899999, "i": "15m", "x": closed,
        "o": "10", "h": "12", "l": "9", "c": "11", "q": "100",
    }}


def test_only_closed_valid_candles():
    assert parse_event(candle_event(False), {"BTCUSDT"}, 1000000) is None
    result = parse_event(candle_event(), {"BTCUSDT"}, 1000000)
    assert isinstance(result, Candle)
    assert result.close == 11
    assert parse_event(candle_event(), {"ETHUSDT"}, 1000000) is None
    assert parse_event(candle_event(), {"BTCUSDT"}, 800000) is None


@pytest.mark.parametrize("field,value", [("c", "NaN"), ("q", "-1"), ("h", "8"), ("t", 1)])
def test_reject_corrupt_candles(field, value):
    event = candle_event()
    event["k"][field] = value
    with pytest.raises(ValueError):
        parse_event(event, {"BTCUSDT"}, 1000000)


def test_wilder_reference_and_warmup():
    closes = [44.34,44.09,44.15,43.61,44.33,44.83,45.1,45.42,45.84,46.08,
              45.89,46.03,45.61,46.28,46.28,46,46.03,46.41,46.22,45.64,46.21]
    values = rsi_series(closes)
    assert values[:14] == [None] * 14
    assert values[14] == pytest.approx(70.464135, abs=1e-6)
    assert values[15] == pytest.approx(66.249619, abs=1e-6)
    assert values[-1] == pytest.approx(62.880718, abs=1e-6)


def test_rsi_edges():
    assert rsi_series([1] * 15)[-1] == 50
    assert rsi_series(list(range(1, 16)))[-1] == 100
    assert rsi_series(list(range(16, 1, -1)))[-1] == 0
    with pytest.raises(ValueError):
        rsi_series([1, math.inf])
