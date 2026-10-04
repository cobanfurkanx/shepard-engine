import pytest

from shepard_engine.market import Candle
from shepard_engine.persistence import advance_state


def test_state_rsi_and_gap_protection():
    state = None
    for i in range(15):
        state, previous = advance_state(state, Candle("BTCUSDT", i * 900000, 10 + i, 100))
    assert state["rsi"] == 100
    assert previous is None
    state, previous = advance_state(state, Candle("BTCUSDT", 15 * 900000, 23, 100))
    assert previous == 100
    assert 0 < state["rsi"] < 100
    with pytest.raises(ValueError, match="gap"):
        advance_state(state, Candle("BTCUSDT", 17 * 900000, 24, 100))


def test_flat_and_downward_state():
    for prices, expected in [([10] * 15, 50), (list(range(20, 5, -1)), 0)]:
        state = None
        for i, price in enumerate(prices):
            state, _ = advance_state(state, Candle("BTCUSDT", i * 900000, price, 10))
        assert state["rsi"] == expected
