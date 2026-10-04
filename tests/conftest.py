import os
from urllib.parse import urlsplit, urlunsplit

import pytest
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict
from redis import Redis

from shepard_engine.database import connect_database, migrate
from shepard_engine.settings import Settings


@pytest.fixture
def integration_settings():
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 and TEST_DATABASE_URL for real infrastructure tests")
    values = dotenv_values(".env.local")
    database_url = os.getenv("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL")
    if not database_url or conninfo_to_dict(database_url).get("dbname") != "engine_test":
        pytest.fail("Tests require the separate engine_test database")
    redis_url = os.getenv("TEST_REDIS_URL") or values.get("ENGINE_REDIS_URL")
    parsed = urlsplit(redis_url)
    redis_url = urlunsplit(parsed._replace(path="/15"))
    settings = Settings(
        database_url=database_url,
        redis_url=redis_url,
        identity_enabled=True,
        jwt_secret="test-only-secret-at-least-32-characters",
        symbols="BTCUSDT",
    )
    migrate(database_url)
    with connect_database(database_url) as connection:
        connection.execute("TRUNCATE engine.candles, engine.indicator_state, engine.users CASCADE")
    redis = Redis.from_url(redis_url, decode_responses=True)
    redis.flushdb()
    yield settings
    redis.flushdb()
    redis.close()
