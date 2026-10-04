import time

import fakeredis
from fastapi.testclient import TestClient

from shepard_engine.api import create_app
from shepard_engine.cache import MarketCache
from shepard_engine.settings import Settings


def test_health_ticker_auth_disabled_and_validation():
    redis = fakeredis.FakeRedis(decode_responses=True)
    client = TestClient(create_app(Settings(), redis=redis))
    assert client.get("/health/live").status_code == 200
    assert client.get("/v1/market/ticker/BTCUSDT").status_code == 503
    cache = MarketCache(redis)
    cache.put_ticker({"symbol": "BTCUSDT", "price": 10, "event_ms": int(time.time() * 1000)})
    result = client.get("/v1/market/ticker/BTCUSDT")
    assert result.status_code == 200
    assert result.json()["price"] == 10
    assert result.headers["x-content-type-options"] == "nosniff"
    assert client.get("/v1/market/ticker/EVILUSDT").status_code == 404
    assert (
        client.post(
            "/v1/auth/login", json={"email": "test@example.com", "password": "whatever"}
        ).status_code
        == 404
    )
    assert client.get("/v1/auth/me").status_code == 404


def test_auth_api_and_rate_limits(integration_settings):
    redis = fakeredis.FakeRedis(decode_responses=True)
    client = TestClient(create_app(integration_settings, redis=redis))
    body = {"email": "test@example.com", "password": "strong-password-123"}
    assert client.post("/v1/auth/register", json=body).status_code == 201
    login = client.post("/v1/auth/login", json=body)
    assert login.status_code == 200
    assert login.headers["cache-control"] == "no-store"
    first = login.json()
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.get("/v1/auth/me", headers=headers).json()["email"] == body["email"]
    rotated = client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code
        == 401
    )
    assert client.get("/v1/auth/me", headers=headers).status_code == 401
    assert client.get("/v1/auth/me").status_code == 401
    assert (
        client.post("/v1/auth/register", json={"email": "bad", "password": "short"}).status_code
        == 422
    )
    assert client.post("/v1/auth/login", content="x" * 5000).status_code == 413
    for _ in range(12):
        response = client.post("/v1/auth/login", json=body)
    assert response.status_code == 429


def test_public_rate_limit():
    client = TestClient(create_app(Settings(), redis=fakeredis.FakeRedis(decode_responses=True)))
    for _ in range(61):
        response = client.get("/v1/market/ticker/BTCUSDT")
    assert response.status_code == 429


def test_dependency_failure_and_chunked_requests(monkeypatch):
    from redis.exceptions import RedisError

    redis = fakeredis.FakeRedis(decode_responses=True)
    client = TestClient(create_app(Settings(), redis=redis))
    assert (
        client.post("/unknown", content="x", headers={"transfer-encoding": "chunked"}).status_code
        == 411
    )

    def fail(*args, **kwargs):
        raise RedisError("private connection details")

    monkeypatch.setattr(redis, "ping", fail)
    assert client.get("/health/ready").json() == {"detail": "service unavailable"}
    monkeypatch.setattr(redis, "eval", fail)
    response = client.get("/v1/market/ticker/BTCUSDT")
    assert response.status_code == 503
    assert "private" not in response.text


def test_logout_endpoint(integration_settings):
    client = TestClient(
        create_app(integration_settings, redis=fakeredis.FakeRedis(decode_responses=True))
    )
    body = {"email": "logout@example.com", "password": "strong-password-123"}
    client.post("/v1/auth/register", json=body)
    token = client.post("/v1/auth/login", json=body).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/v1/auth/me", headers=headers).status_code == 401
