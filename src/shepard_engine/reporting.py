from shepard_engine.database import sql_file
from shepard_engine.market import INTERVAL_MS
from shepard_engine.settings import get_settings


def market_report(connection, end_ms: int, symbols=None):
    if end_ms <= 0 or end_ms % INTERVAL_MS:
        raise ValueError("report boundary must be aligned to closed 15m candles")
    return connection.execute(
        sql_file("top_coins.sql"),
        {"end_ms": end_ms, "symbols": sorted(symbols or get_settings().symbol_set)},
    ).fetchall()


def report_boundary(connection, symbols, now_ms):
    rows = connection.execute(
        """
        SELECT symbol, max(open_ms) AS latest FROM engine.candles
        WHERE symbol = ANY(%s) GROUP BY symbol
    """,
        (sorted(symbols),),
    ).fetchall()
    if len(rows) != len(symbols):
        raise ValueError("market report warming up")
    end_ms = min(row["latest"] for row in rows) + INTERVAL_MS
    if end_ms > now_ms or now_ms - end_ms > 2 * INTERVAL_MS:
        raise ValueError("market report stale")
    return end_ms
