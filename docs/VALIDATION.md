# Validation — 2026-10-04

## Local engine

- Python 3.12.14: 30 tests passed; branch-inclusive coverage 96.15%, gate 85%.
- Real PostgreSQL 17 and Redis 7 integration: isolated engine_test and Redis DB 15.
- Ruff lint and format passed. Source distribution and wheel built successfully.
- Locked runtime dependency audit: no known vulnerabilities found.
- Docker image built; six services running. PostgreSQL, Redis and API healthy.
- Real Binance WebSocket connected after REST recovery; five symbols, 399 closed candles each.
- Celery job persisted 1,995 candles to the isolated engine database.
- Repeated Celery delivery inserted zero duplicates; ingester restart recovered and restored market health.
- HTTP /health/ready, /health/market, BTCUSDT ticker and top-coins: 200.
- Empty top-coins response is valid: no fabricated qualifying matches.
- SQL EXPLAIN ANALYZE: 53,760 synthetic candles, 0.467 ms local execution; see QUERY_PLAN.md.

## Existing app

- Eight database/retention/deployment tests and nine Deno tests passed after merging current main.
- Three real Edge browser tests passed: disabled feature, rows/empty/mobile, outage/retry.
- Frontend and seven Edge Function typechecks passed. Production build passed; lint has no errors and 12 pre-existing warnings.
- Engine integration defaults to disabled. No Supabase schema, authentication, billing or analysis changes.

## Scope and review

Reviewed input validation, refresh reuse/concurrency, transaction lock ordering, SQL parameterization,
idempotent delivery, freshness checks, bounded recovery/retention, token isolation and container restrictions.
Independent identity is a reference demo; internet deployment still requires the controls in OPERATIONS.md.
No production deployment or live orders. GitHub CI evidence is linked by the README badge.

Backend GitHub Actions [run 37200805845](https://github.com/cobanfurkanx/shepard-engine/actions/runs/37200805845)
passed on Linux: all 30 tests, 96.15% coverage, lint, format, wheel and Docker image build.
App integration is reviewable in [PR 1](https://github.com/cobanfurkanx/shepardai-crypto-advisor/pull/1).
