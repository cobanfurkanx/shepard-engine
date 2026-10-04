import time

import pytest
from fastapi.testclient import TestClient
from redis import Redis

from shepard_engine.api import create_app
from shepard_engine.cache import MarketCache
from shepard_engine.database import connect_database
from shepard_engine.market import INTERVAL_MS, Candle
from shepard_engine.reporting import market_report, report_boundary
from shepard_engine.worker import get_settings, persist_market, process_market, retention

pytestmark = pytest.mark.integration


def test_real_cache_to_worker_to_api(integration_settings, monkeypatch):
    settings = integration_settings
    redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True)
    cache = MarketCache(redis)
    end_ms = int(time.time() * 1000) // INTERVAL_MS * INTERVAL_MS
    for i in range(210):
        cache.put_candle(Candle("BTCUSDT", end_ms - (210 - i) * INTERVAL_MS, 50 + i % 7, 100))
    redis.set("engine:ingestion_alive", str(time.time()), ex=60)
    monkeypatch.setattr("shepard_engine.worker.get_settings", lambda: settings)
    assert persist_market.run() == 210
    assert process_market(settings) == 0
    client = TestClient(create_app(settings, redis=redis))
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/market").status_code == 200
    report = client.get("/v1/market/top-coins")
    assert report.status_code == 200
    assert report.json()["as_of_ms"] == end_ms
    assert report.json()["items"] == []  # No fabricated matches.
    redis.delete("engine:worker_alive")
    assert client.get("/health/market").status_code == 503
    redis.delete("engine:candles:BTCUSDT")
    with pytest.raises(ValueError, match="unavailable"):
        process_market(settings)
    redis.close()


def test_retention_and_report_staleness(integration_settings, monkeypatch):
    settings = integration_settings
    monkeypatch.setattr("shepard_engine.worker.get_settings", lambda: settings)
    url = settings.database_url.get_secret_value()
    with connect_database(url) as connection:
        connection.execute("""
            INSERT INTO engine.candles(symbol,open_ms,close,quote_volume)
            VALUES ('BTCUSDT',0,10,1)
        """)
        with pytest.raises(ValueError, match="stale"):
            report_boundary(connection, {"BTCUSDT"}, int(time.time() * 1000))
        with pytest.raises(ValueError, match="warming"):
            report_boundary(connection, {"BTCUSDT", "ETHUSDT"}, int(time.time() * 1000))
        with pytest.raises(ValueError, match="aligned"):
            market_report(connection, 1)
    assert retention.run() == 1
    client = TestClient(create_app(settings))
    with client:
        assert client.get("/v1/market/top-coins").status_code == 503
    assert get_settings() is not None
