"""Only public exchange endpoints; no trading credentials or order methods."""

import asyncio
import json
import logging
import random
import time

import httpx
from redis import Redis
from redis.exceptions import RedisError
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from shepard_engine.cache import MarketCache
from shepard_engine.market import Candle, parse_event
from shepard_engine.settings import get_settings

logger = logging.getLogger(__name__)


def stream_url(symbols):
    streams = [f"{s.lower()}@{kind}" for s in sorted(symbols) for kind in ("ticker", "kline_15m")]
    return "wss://stream.binance.com:9443/stream?streams=" + "/".join(streams)


async def backfill(client, cache, symbols, now_ms=None):
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    for symbol in sorted(symbols):
        response = await client.get("https://data-api.binance.vision/api/v3/klines",
                                    params={"symbol": symbol, "interval": "15m", "limit": 400})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("invalid recovery payload")
        for row in rows:
            event = {"e": "kline", "s": symbol, "k": {
                "t": row[0], "T": row[6], "i": "15m", "x": True,
                "o": row[1], "h": row[2], "l": row[3], "c": row[4], "q": row[7],
            }}
            candle = parse_event(event, symbols, now_ms)
            if isinstance(candle, Candle):
                cache.put_candle(candle)


def consume_message(message, cache, symbols, now_ms):
    try:
        event = json.loads(message)
        if not isinstance(event, dict):
            return False
        result = parse_event(event, symbols, now_ms)
        if isinstance(result, Candle):
            cache.put_candle(result)
        elif result:
            cache.put_ticker(result)
        return result is not None
    except (ValueError, KeyError, TypeError, OverflowError):
        logger.warning("exchange_message_rejected")
        return False


async def run(settings=None, *, stop=None, connector=connect, sleep=asyncio.sleep):
    settings = settings or get_settings()
    stop = stop or asyncio.Event()
    redis = Redis.from_url(settings.redis_url.get_secret_value(), decode_responses=True,
                          socket_timeout=5, socket_connect_timeout=5)
    cache = MarketCache(redis)
    delay = 1
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            while not stop.is_set():
                try:
                    # Open socket first: server messages queue while REST repairs downtime gaps.
                    async with connector(stream_url(settings.symbol_set), max_queue=128,
                                         max_size=65536, open_timeout=15,
                                         ping_interval=20, ping_timeout=20) as socket:
                        await backfill(client, cache, settings.symbol_set)
                        delay = 1
                        logger.info("exchange_connected")
                        async for message in socket:
                            accepted = consume_message(message, cache, settings.symbol_set,
                                                       int(time.time() * 1000))
                            if accepted:
                                redis.set("engine:ingestion_alive", str(time.time()), ex=60)
                            if stop.is_set():
                                break
                except (OSError, WebSocketException, httpx.HTTPError, RedisError,
                        ValueError, IndexError, TypeError):
                    logger.warning("exchange_reconnect", extra={"delay_seconds": delay})
                    await sleep(delay + random.uniform(0, 1))
                    delay = min(delay * 2, 60)
    finally:
        redis.close()


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(run())


if __name__ == "__main__":
    main()
