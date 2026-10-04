import asyncio
import json
from unittest.mock import AsyncMock

import fakeredis
import httpx
import pytest

from shepard_engine.cache import MarketCache
from shepard_engine.ingestion import backfill, consume_message, run, stream_url
from shepard_engine.settings import Settings


def test_backfill_excludes_open_candles():
    rows = [
        [0, "10", "12", "9", "11", "1", 899999, "100"],
        [900000, "10", "12", "9", "11", "1", 1799999, "100"],
    ]

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
    payload = {"data": {"e": "24hrTicker", "s": "BTCUSDT", "E": 1000000, "c": "10"}}
    assert consume_message(json.dumps(payload), cache, {"BTCUSDT"}, 1000000)
    assert cache.ticker("BTCUSDT")["price"] == 10


def test_configuration_restricts_streams():
    assert "btcusdt@kline_15m" in stream_url({"BTCUSDT"})
    with pytest.raises(ValueError):
        Settings(symbols="BTCUSDT/../../evil")
    with pytest.raises(ValueError):
        Settings(identity_enabled=True, jwt_secret="short")
    with pytest.raises(ValueError):
        Settings(symbols="BTCUSDT,BTCUSDT")


def test_reconnect_recovers_before_processing_messages(monkeypatch):
    async def exercise():
        import time

        cache_redis = fakeredis.FakeRedis(decode_responses=True)
        monkeypatch.setattr("shepard_engine.ingestion.Redis.from_url", lambda *a, **kw: cache_redis)
        recovered = AsyncMock()
        monkeypatch.setattr("shepard_engine.ingestion.backfill", recovered)
        monkeypatch.setattr("shepard_engine.ingestion.clock_offset", AsyncMock(return_value=0))
        monkeypatch.setattr("shepard_engine.ingestion.get_settings", lambda: Settings())
        stop = asyncio.Event()
        calls, delays = [], []

        class Socket:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def __aiter__(self):
                assert recovered.await_count == 1
                yield "{}"
                stop.set()
                yield json.dumps(
                    {"e": "24hrTicker", "s": "BTCUSDT", "E": int(time.time() * 1000), "c": "10"}
                )

        def connector(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                raise OSError("network unavailable")
            return Socket()

        async def sleep(delay):
            delays.append(delay)

        await run(stop=stop, connector=connector, sleep=sleep)
        assert len(calls) == 2
        assert 1 <= delays[0] <= 2
        assert cache_redis.get("engine:ingestion_alive")

    asyncio.run(exercise())


def test_exchange_clock_calibration(monkeypatch):
    from shepard_engine.ingestion import clock_offset

    monkeypatch.setattr("shepard_engine.ingestion.time.time", lambda: 1000.0)

    async def exercise():
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"serverTime": 1010000})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            assert await clock_offset(client) == 10000

    asyncio.run(exercise())


def test_backfill_rejects_non_array_payload():
    async def exercise():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"error": True}))
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(ValueError):
                await backfill(client, MarketCache(fakeredis.FakeRedis()), {"BTCUSDT"})

    asyncio.run(exercise())
