"""Benchmark synthetic fixtures only in engine_test; rolls fixture changes back."""

import json
import os
import time
from pathlib import Path

from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict

from shepard_engine.database import connect_database, migrate, sql_file

values = dotenv_values(".env.local")
url = os.getenv("TEST_DATABASE_URL") or values.get("TEST_DATABASE_URL")
if not url or conninfo_to_dict(url).get("dbname") != "engine_test":
    raise SystemExit("Only engine_test is permitted")
migrate(url)
end_ms = int(time.time() * 1000) // 900000 * 900000
with connect_database(url) as connection:
    connection.execute("TRUNCATE engine.candles")
    connection.execute(
        """
        INSERT INTO engine.candles(symbol,open_ms,close,quote_volume,rsi,previous_rsi)
        SELECT 'COIN' || symbol::text || 'USDT', %s - (2688-candle)*900000::bigint, 10,
               CASE WHEN candle >= 2592 THEN 150 ELSE 100 END,
               CASE WHEN candle %% 10 = 0 THEN 20 ELSE 50 END,
               CASE WHEN (candle-1) %% 10 = 0 THEN 20 ELSE 50 END
        FROM generate_series(1,20) symbol CROSS JOIN generate_series(0,2687) candle
    """,
        (end_ms,),
    )
    connection.execute("ANALYZE engine.candles")
    params = {"end_ms": end_ms, "symbols": [f"COIN{i}USDT" for i in range(1, 6)]}
    plan = connection.execute(
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql_file("top_coins.sql"), params
    ).fetchone()["QUERY PLAN"][0]
    connection.rollback()
target = Path("docs/QUERY_PLAN.md")
target.write_text(
    "# Query plan evidence\n\n"
    "Local PostgreSQL, 53,760 synthetic candles (20 symbols, 28 days), five selected symbols. "
    "Fixtures ran in engine_test and were rolled back. "
    "This is local evidence, not a production SLA.\n\n"
    f"Execution: {plan['Execution Time']:.3f} ms. Planning: {plan['Planning Time']:.3f} ms.\n\n"
    "The time-window covering index bounds the 48-hour input; the primary key provides uniqueness "
    "and ordered per-symbol state access. Complete-window and positive-volume filters preserve "
    "correctness before ranking. PostgreSQL may choose sequential scans on small tables.\n\n"
    "Reproduce: `uv run python scripts/query_plan.py`.\n\n```json\n"
    + json.dumps(plan, indent=2)
    + "\n```\n",
    encoding="utf-8",
)
print(f"Query plan saved: {plan['Execution Time']:.3f} ms")
