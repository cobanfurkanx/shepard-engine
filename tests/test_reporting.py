from concurrent.futures import ThreadPoolExecutor

import pytest

from shepard_engine.database import connect_database, sql_file
from shepard_engine.market import Candle, rsi_series
from shepard_engine.persistence import persist_candles
from shepard_engine.reporting import market_report

pytestmark = pytest.mark.integration


def test_persistence_retry_concurrency_and_incremental_rsi(integration_settings):
    url = integration_settings.database_url.get_secret_value()
    closes = [50 + ((i * 7) % 13) for i in range(50)]
    candles = [Candle("BTCUSDT", i * 900000, price, 100) for i, price in enumerate(closes)]

    def persist(batch):
        with connect_database(url) as connection:
            return persist_candles(connection, "BTCUSDT", batch)

    assert persist(candles[:20]) == 20
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(persist, [candles, candles]))
    assert sum(counts) == 30
    with connect_database(url) as connection:
        rows = connection.execute("SELECT * FROM engine.candles ORDER BY open_ms").fetchall()
    assert len(rows) == 50
    assert [r["rsi"] for r in rows] == pytest.approx(rsi_series(closes))
    with pytest.raises(ValueError, match="gap"):
        persist([Candle("BTCUSDT", 51 * 900000, 10, 100)])
    with pytest.raises(ValueError, match="mixed"):
        persist([Candle("ETHUSDT", 50 * 900000, 10, 100)])


def test_sql_crossings_volume_and_incomplete_windows(integration_settings):
    url = integration_settings.database_url.get_secret_value()
    end_ms = 200 * 900000
    rows = []
    # BTC passes, ETH has missing historical candle, SOL volume grows only 49%.
    for symbol, recent_volume in [("BTCUSDT", 150), ("ETHUSDT", 200), ("SOLUSDT", 149)]:
        for i in range(192):
            if symbol == "ETHUSDT" and i == 0:
                continue
            recent = i >= 96
            crossing = recent and i % 10 == 0
            rows.append(
                (
                    symbol,
                    end_ms - (192 - i) * 900000,
                    10,
                    recent_volume if recent else 100,
                    20 if recent else 50,
                    50 if crossing else 20,
                )
            )
    with connect_database(url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO engine.candles(symbol,open_ms,close,quote_volume,rsi,previous_rsi)
                VALUES (%s,%s,%s,%s,%s,%s)
            """,
                rows,
            )
        result = market_report(connection, end_ms)
        assert len(result) == 1
        assert result[0]["symbol"] == "BTCUSDT"
        assert result[0]["crossings"] == 10
        assert result[0]["volume_growth_pct"] == pytest.approx(50)
        plan = connection.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql_file("top_coins.sql"),
            {"end_ms": end_ms, "symbols": sorted(integration_settings.symbol_set)},
        ).fetchone()
        assert plan["QUERY PLAN"][0]["Execution Time"] >= 0
