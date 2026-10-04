-- Consecutive non-overlapping UTC windows of 96 closed 15m candles (24h each).
-- Count transitions >=30 to <30, not every below-threshold observation.
WITH window_stats AS (
  SELECT symbol,
    count(*) FILTER (WHERE open_ms >= %(end_ms)s - 86400000) AS recent_count,
    count(*) FILTER (WHERE open_ms < %(end_ms)s - 86400000) AS previous_count,
    sum(quote_volume) FILTER (WHERE open_ms >= %(end_ms)s - 86400000) AS recent_volume,
    sum(quote_volume) FILTER (WHERE open_ms < %(end_ms)s - 86400000) AS previous_volume,
    count(*) FILTER (WHERE open_ms >= %(end_ms)s - 86400000
                    AND rsi < 30 AND previous_rsi >= 30) AS crossings
  FROM engine.candles
  WHERE open_ms >= %(end_ms)s - 172800000 AND open_ms < %(end_ms)s
    AND symbol = ANY(%(symbols)s)
  GROUP BY symbol
)
SELECT symbol, crossings, recent_volume, previous_volume,
       (recent_volume / previous_volume - 1) * 100 AS volume_growth_pct
FROM window_stats
WHERE recent_count = 96 AND previous_count = 96 AND previous_volume > 0
  AND recent_volume >= previous_volume * 1.5 AND crossings > 0
ORDER BY crossings DESC, volume_growth_pct DESC, symbol ASC
LIMIT 5;
