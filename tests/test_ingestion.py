import asyncio
import json

import fakeredis
import httpx
import pytest

from shepard_engine.cache import MarketCache
from shepard_engine.ingestion import backfill, consume_message, stream_url
from shepard_engine.settings import Settings


def test_backfill_excludes_open_candles():
    rows = [[0,"10","12","9","11","1",899999,"100"],
            [900000,"10","12","9","11","1",1799999,"100"]]
    async def exercise():
        cache = MarketCache(fakeredis.FakeRedis(decode_responses=True))
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json=rows))
        async with httpx.AsyncClient(transport=transport) as client:
            await backfill(client, cache, {"BTCUSDT"}, now_ms=1000000)
        assert len(cache.candles("BTCUSDT")) == 1
    asyncio.run(exercise())


def test_invalid_messages_cannot_stop_ingestion():
    cache = MarketCache(fakeredis.FakeRedis(decode_responses=True))
    assert not consume_message("{", cache, {"BTCUSDT"}, 1000000)
    assert not consume_message("[]", cache, {"BTCUSDT"}, 1000000)
    payload = {"data": {"e":"24hrTicker","s":"BTCUSDT","E":1000000,"c":"10"}}
    assert consume_message(json.dumps(payload), cache, {"BTCUSDT"}, 1000000)
    assert cache.ticker("BTCUSDT")["price"] == 10


def test_configuration_restricts_streams():
    assert "btcusdt@kline_15m" in stream_url({"BTCUSDT"})
    with pytest.raises(ValueError):
        Settings(symbols="BTCUSDT/../../evil")
    with pytest.raises(ValueError):
        Settings(identity_enabled=True, jwt_secret="short")
