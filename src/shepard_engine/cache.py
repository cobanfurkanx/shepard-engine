import hashlib
import json

from redis import Redis

from shepard_engine.market import INTERVAL_MS, Candle

CANDLE_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], ARGV[1], ARGV[1])
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[2])
redis.call('ZREMRANGEBYRANK', KEYS[1], 0, -tonumber(ARGV[3])-1)
redis.call('EXPIRE', KEYS[1], 432000)
return 1
"""
TICKER_LUA = """
local old = redis.call('GET', KEYS[1])
if old and cjson.decode(old).event_ms > tonumber(ARGV[1]) then return 0 end
redis.call('SET', KEYS[1], ARGV[2], 'EX', 60)
return 1
"""
RATE_LUA = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return n
"""


class MarketCache:
    def __init__(self, redis: Redis, history=400):
        self.redis = redis
        self.history = history

    def put_candle(self, candle: Candle):
        self.redis.eval(
            CANDLE_LUA,
            1,
            f"engine:candles:{candle.symbol}",
            candle.open_ms,
            json.dumps(candle.to_dict()),
            self.history,
        )

    def put_ticker(self, ticker: dict):
        self.redis.eval(
            TICKER_LUA,
            1,
            f"engine:ticker:{ticker['symbol']}",
            ticker["event_ms"],
            json.dumps(ticker),
        )

    def ticker(self, symbol):
        raw = self.redis.get(f"engine:ticker:{symbol}")
        return json.loads(raw) if raw else None

    def candles(self, symbol) -> list[Candle]:
        rows = self.redis.zrange(f"engine:candles:{symbol}", 0, -1)
        candles = [Candle(**json.loads(row)) for row in rows]
        if any(
            b.open_ms - a.open_ms != INTERVAL_MS for a, b in zip(candles, candles[1:], strict=False)
        ):
            raise ValueError("candle history gap; recovery required")
        return candles


def allow_request(redis: Redis, identity: str, limit: int, seconds: int):
    # Hash identifiers so cache keys do not store email addresses or IP addresses in plain text.
    key = hashlib.sha256(identity.encode()).hexdigest()
    return redis.eval(RATE_LUA, 1, f"engine:rate:{key}", seconds) <= limit
