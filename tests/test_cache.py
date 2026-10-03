import fakeredis
import pytest

from shepard_engine.cache import MarketCache, allow_request
from shepard_engine.market import Candle


def test_cache_replaces_duplicate_candle_and_bounds_memory():
    cache = MarketCache(fakeredis.FakeRedis(decode_responses=True), history=3)
    for i in range(5):
        cache.put_candle(Candle("BTCUSDT", i * 900000, 10+i, 100))
    cache.put_candle(Candle("BTCUSDT", 4*900000, 15, 100))
    assert [c.close for c in cache.candles("BTCUSDT")] == [12, 13, 15]
    assert cache.redis.ttl("engine:candles:BTCUSDT") > 0


def test_ticker_ordering_and_shared_limiter():
    cache = MarketCache(fakeredis.FakeRedis(decode_responses=True))
    cache.put_ticker({"symbol": "BTCUSDT", "price": 10, "event_ms": 20})
    cache.put_ticker({"symbol": "BTCUSDT", "price": 9, "event_ms": 10})
    assert cache.ticker("BTCUSDT")["price"] == 10
    assert allow_request(cache.redis, "test", 2, 60)
    assert allow_request(cache.redis, "test", 2, 60)
    assert not allow_request(cache.redis, "test", 2, 60)


def test_gaps_are_not_valid_indicator_history():
    cache = MarketCache(fakeredis.FakeRedis(decode_responses=True))
    cache.put_candle(Candle("BTCUSDT", 0, 10, 1))
    cache.put_candle(Candle("BTCUSDT", 1800000, 11, 1))
    with pytest.raises(ValueError, match="gap"):
        cache.candles("BTCUSDT")
