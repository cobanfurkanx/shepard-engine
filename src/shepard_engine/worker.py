import logging
import time

import psycopg
from celery import Celery
from redis import Redis
from redis.exceptions import RedisError

from shepard_engine.cache import MarketCache
from shepard_engine.database import connect_database
from shepard_engine.persistence import persist_candles
from shepard_engine.settings import get_settings

settings = get_settings()
app = Celery("shepard_engine", broker=settings.redis_url.get_secret_value())
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 3600},
    task_soft_time_limit=240,
    task_time_limit=300,
    timezone="UTC",
    beat_schedule={
        "market-15m": {"task": "engine.persist_market", "schedule": 900.0},
        "retention": {"task": "engine.retention", "schedule": 3600.0},
    },
)
logger = logging.getLogger(__name__)


def process_market(settings):
    with Redis.from_url(
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
    ) as redis:
        cache = MarketCache(redis)
        total = 0
        for symbol in sorted(settings.symbol_set):
            candles = cache.candles(symbol)
            now_ms = int(time.time() * 1000) + int(
                redis.get("engine:exchange_clock_offset_ms") or 0
            )
            if not candles or now_ms - candles[-1].open_ms > 2 * 900000:
                raise ValueError("market history unavailable or stale")
            with connect_database(settings.database_url.get_secret_value()) as connection:
                total += persist_candles(connection, symbol, candles)
        redis.set("engine:worker_alive", str(time.time()), ex=1800)
        logger.info("market_persisted", extra={"rows": total})
        return total


@app.task(
    name="engine.persist_market",
    autoretry_for=(psycopg.OperationalError, RedisError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def persist_market():
    return process_market(get_settings())


@app.task(
    name="engine.retention",
    autoretry_for=(psycopg.OperationalError,),
    retry_backoff=True,
    max_retries=3,
)
def retention():
    settings = get_settings()
    cutoff = int((time.time() - settings.retention_days * 86400) * 1000)
    with connect_database(settings.database_url.get_secret_value()) as connection:
        # Bounded deletion keeps lock/WAL pressure small. Repeat hourly.
        deleted = connection.execute(
            """
            DELETE FROM engine.candles WHERE (symbol, open_ms) IN
              (SELECT symbol, open_ms FROM engine.candles WHERE open_ms < %s LIMIT 10000)
        """,
            (cutoff,),
        ).rowcount
        connection.execute("DELETE FROM engine.sessions WHERE expires_at < now()")
    return deleted
