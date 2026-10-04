# Query plan evidence

Local PostgreSQL, 53,760 synthetic candles (20 symbols, 28 days), five selected symbols. Fixtures ran in engine_test and were rolled back. This is local evidence, not a production SLA.

Execution: 0.467 ms. Planning: 0.763 ms.

This run used a bitmap scan of candles_pkey, bounded by selected symbols and the 48-hour window. A separate time-window covering index is also available. Complete-window and positive-volume filters preserve correctness before ranking. PostgreSQL may choose sequential scans on small tables.

Reproduce: `uv run python scripts/query_plan.py`.

```json
{
  "Plan": {
    "Node Type": "Limit",
    "Parallel Aware": false,
    "Async Capable": false,
    "Startup Cost": 677.75,
    "Total Cost": 677.75,
    "Plan Rows": 1,
    "Plan Width": 42,
    "Actual Startup Time": 0.354,
    "Actual Total Time": 0.355,
    "Actual Rows": 5,
    "Actual Loops": 1,
    "Shared Hit Blocks": 34,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0,
    "Plans": [
      {
        "Node Type": "Sort",
        "Parent Relationship": "Outer",
        "Parallel Aware": false,
        "Async Capable": false,
        "Startup Cost": 677.75,
        "Total Cost": 677.75,
        "Plan Rows": 1,
        "Plan Width": 42,
        "Actual Startup Time": 0.353,
        "Actual Total Time": 0.354,
        "Actual Rows": 5,
        "Actual Loops": 1,
        "Sort Key": [
          "window_stats.crossings DESC",
          "((((window_stats.recent_volume / window_stats.previous_volume) - '1'::double precision) * '100'::double precision)) DESC",
          "window_stats.symbol"
        ],
        "Sort Method": "quicksort",
        "Sort Space Used": 25,
        "Sort Space Type": "Memory",
        "Shared Hit Blocks": 34,
        "Shared Read Blocks": 0,
        "Shared Dirtied Blocks": 0,
        "Shared Written Blocks": 0,
        "Local Hit Blocks": 0,
        "Local Read Blocks": 0,
        "Local Dirtied Blocks": 0,
        "Local Written Blocks": 0,
        "Temp Read Blocks": 0,
        "Temp Written Blocks": 0,
        "Plans": [
          {
            "Node Type": "Subquery Scan",
            "Parent Relationship": "Outer",
            "Parallel Aware": false,
            "Async Capable": false,
            "Alias": "window_stats",
            "Startup Cost": 677.22,
            "Total Cost": 677.74,
            "Plan Rows": 1,
            "Plan Width": 42,
            "Actual Startup Time": 0.325,
            "Actual Total Time": 0.327,
            "Actual Rows": 5,
            "Actual Loops": 1,
            "Shared Hit Blocks": 34,
            "Shared Read Blocks": 0,
            "Shared Dirtied Blocks": 0,
            "Shared Written Blocks": 0,
            "Local Hit Blocks": 0,
            "Local Read Blocks": 0,
            "Local Dirtied Blocks": 0,
            "Local Written Blocks": 0,
            "Temp Read Blocks": 0,
            "Temp Written Blocks": 0,
            "Plans": [
              {
                "Node Type": "Aggregate",
                "Strategy": "Hashed",
                "Partial Mode": "Simple",
                "Parent Relationship": "Subquery",
                "Parallel Aware": false,
                "Async Capable": false,
                "Startup Cost": 677.22,
                "Total Cost": 677.72,
                "Plan Rows": 1,
                "Plan Width": 50,
                "Actual Startup Time": 0.324,
                "Actual Total Time": 0.326,
                "Actual Rows": 5,
                "Actual Loops": 1,
                "Group Key": [
                  "candles.symbol"
                ],
                "Filter": "((sum(candles.quote_volume) FILTER (WHERE (candles.open_ms < '1791028800000'::bigint)) > '0'::double precision) AND (count(*) FILTER (WHERE ((candles.open_ms >= '1791028800000'::bigint) AND (candles.rsi < '30'::double precision) AND (candles.previous_rsi >= '30'::double precision))) > 0) AND (count(*) FILTER (WHERE (candles.open_ms >= '1791028800000'::bigint)) = 96) AND (count(*) FILTER (WHERE (candles.open_ms < '1791028800000'::bigint)) = 96) AND (sum(candles.quote_volume) FILTER (WHERE (candles.open_ms >= '1791028800000'::bigint)) >= (sum(candles.quote_volume) FILTER (WHERE (candles.open_ms < '1791028800000'::bigint)) * '1.5'::double precision)))",
                "Planned Partitions": 0,
                "HashAgg Batches": 1,
                "Peak Memory Usage": 24,
                "Disk Usage": 0,
                "Rows Removed by Filter": 0,
                "Shared Hit Blocks": 34,
                "Shared Read Blocks": 0,
                "Shared Dirtied Blocks": 0,
                "Shared Written Blocks": 0,
                "Local Hit Blocks": 0,
                "Local Read Blocks": 0,
                "Local Dirtied Blocks": 0,
                "Local Written Blocks": 0,
                "Temp Read Blocks": 0,
                "Temp Written Blocks": 0,
                "Plans": [
                  {
                    "Node Type": "Bitmap Heap Scan",
                    "Parent Relationship": "Outer",
                    "Parallel Aware": false,
                    "Async Capable": false,
                    "Relation Name": "candles",
                    "Alias": "candles",
                    "Startup Cost": 54.44,
                    "Total Cost": 645.73,
                    "Plan Rows": 969,
                    "Plan Width": 42,
                    "Actual Startup Time": 0.098,
                    "Actual Total Time": 0.16,
                    "Actual Rows": 960,
                    "Actual Loops": 1,
                    "Recheck Cond": "((symbol = ANY ('{COIN1USDT,COIN2USDT,COIN3USDT,COIN4USDT,COIN5USDT}'::text[])) AND (open_ms >= '1790942400000'::bigint) AND (open_ms < '1791115200000'::bigint))",
                    "Rows Removed by Index Recheck": 0,
                    "Exact Heap Blocks": 15,
                    "Lossy Heap Blocks": 0,
                    "Shared Hit Blocks": 34,
                    "Shared Read Blocks": 0,
                    "Shared Dirtied Blocks": 0,
                    "Shared Written Blocks": 0,
                    "Local Hit Blocks": 0,
                    "Local Read Blocks": 0,
                    "Local Dirtied Blocks": 0,
                    "Local Written Blocks": 0,
                    "Temp Read Blocks": 0,
                    "Temp Written Blocks": 0,
                    "Plans": [
                      {
                        "Node Type": "Bitmap Index Scan",
                        "Parent Relationship": "Outer",
                        "Parallel Aware": false,
                        "Async Capable": false,
                        "Index Name": "candles_pkey",
                        "Startup Cost": 0.0,
                        "Total Cost": 54.2,
                        "Plan Rows": 969,
                        "Plan Width": 0,
                        "Actual Startup Time": 0.09,
                        "Actual Total Time": 0.09,
                        "Actual Rows": 960,
                        "Actual Loops": 1,
                        "Index Cond": "((symbol = ANY ('{COIN1USDT,COIN2USDT,COIN3USDT,COIN4USDT,COIN5USDT}'::text[])) AND (open_ms >= '1790942400000'::bigint) AND (open_ms < '1791115200000'::bigint))",
                        "Shared Hit Blocks": 19,
                        "Shared Read Blocks": 0,
                        "Shared Dirtied Blocks": 0,
                        "Shared Written Blocks": 0,
                        "Local Hit Blocks": 0,
                        "Local Read Blocks": 0,
                        "Local Dirtied Blocks": 0,
                        "Local Written Blocks": 0,
                        "Temp Read Blocks": 0,
                        "Temp Written Blocks": 0
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  },
  "Planning": {
    "Shared Hit Blocks": 71,
    "Shared Read Blocks": 0,
    "Shared Dirtied Blocks": 0,
    "Shared Written Blocks": 0,
    "Local Hit Blocks": 0,
    "Local Read Blocks": 0,
    "Local Dirtied Blocks": 0,
    "Local Written Blocks": 0,
    "Temp Read Blocks": 0,
    "Temp Written Blocks": 0
  },
  "Planning Time": 0.763,
  "Triggers": [],
  "Execution Time": 0.467
}
```
