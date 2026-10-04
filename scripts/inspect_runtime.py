import json
import time

from redis import Redis

from shepard_engine.cache import MarketCache
from shepard_engine.database import connect_database
from shepard_engine.settings import get_settings

settings = get_settings()
with Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True) as redis:
    cache = MarketCache(redis)
    print(
        json.dumps(
            {
                "now_ms": int(time.time() * 1000),
                "ingestion_alive": bool(redis.get("engine:ingestion_alive")),
                "worker_alive": bool(redis.get("engine:worker_alive")),
                "tickers": {s: cache.ticker(s) for s in sorted(settings.symbol_set)},
                "candle_counts": {s: len(cache.candles(s)) for s in sorted(settings.symbol_set)},
            }
        )
    )
with connect_database(settings.database_url.get_secret_value()) as connection:
    print(
        json.dumps(
            connection.execute(
                "SELECT symbol,count(*) AS rows FROM engine.candles GROUP BY symbol"
            ).fetchall()
        )
    )
