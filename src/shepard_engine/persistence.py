from dataclasses import asdict

from shepard_engine.market import INTERVAL_MS, Candle, rsi_value


def advance_state(state, candle: Candle):
    if state is None:
        return {
            "symbol": candle.symbol,
            "open_ms": candle.open_ms,
            "close": candle.close,
            "gain": 0.0,
            "loss": 0.0,
            "samples": 0,
            "rsi": None,
        }, None
    if candle.open_ms != state["open_ms"] + INTERVAL_MS:
        raise ValueError("candle gap exceeds recovery history; operator recovery required")
    change = candle.close - state["close"]
    samples = state["samples"] + 1
    up, down = max(change, 0), max(-change, 0)
    if samples <= 14:
        gain, loss = state["gain"] + up / 14, state["loss"] + down / 14
    else:
        gain, loss = (state["gain"] * 13 + up) / 14, (state["loss"] * 13 + down) / 14
    return {
        "symbol": candle.symbol,
        "open_ms": candle.open_ms,
        "close": candle.close,
        "gain": gain,
        "loss": loss,
        "samples": samples,
        "rsi": rsi_value(gain, loss) if samples >= 14 else None,
    }, state["rsi"]


def persist_candles(connection, symbol: str, candles: list[Candle]):
    if any(c.symbol != symbol for c in candles):
        raise ValueError("mixed symbol history")
    # PostgreSQL transaction lock covers concurrent deliveries from all worker processes.
    connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (symbol,))
    state = connection.execute(
        "SELECT * FROM engine.indicator_state WHERE symbol=%s", (symbol,)
    ).fetchone()
    inserted = 0
    for candle in candles:
        if state and candle.open_ms <= state["open_ms"]:
            continue
        state, previous = advance_state(state, candle)
        row = asdict(candle) | {"rsi": state["rsi"], "previous_rsi": previous}
        connection.execute(
            """
            INSERT INTO engine.candles(symbol, open_ms, close, quote_volume, rsi, previous_rsi)
            VALUES (%(symbol)s, %(open_ms)s, %(close)s, %(quote_volume)s, %(rsi)s, %(previous_rsi)s)
            ON CONFLICT (symbol, open_ms) DO NOTHING
        """,
            row,
        )
        inserted += 1
    if inserted:
        connection.execute(
            """
            INSERT INTO engine.indicator_state(symbol, open_ms, close, gain, loss, samples, rsi)
            VALUES (%(symbol)s, %(open_ms)s, %(close)s, %(gain)s, %(loss)s, %(samples)s, %(rsi)s)
            ON CONFLICT (symbol) DO UPDATE SET open_ms=EXCLUDED.open_ms, close=EXCLUDED.close,
              gain=EXCLUDED.gain, loss=EXCLUDED.loss, samples=EXCLUDED.samples, rsi=EXCLUDED.rsi
        """,
            state,
        )
    return inserted
