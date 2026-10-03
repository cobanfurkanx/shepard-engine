# Independent engine contract

Approved scope: additive market worker and standalone identity demonstration. Existing Supabase Auth, billing, Edge Functions and production data remain authoritative. No deployment or production schema migration is part of local implementation.

Modules/build order: market ingestion → indicators/persistence → identity → reports/API → CI/operations → disabled application integration.

Acceptance:
- Public Binance ticker and closed 15-minute kline streams buffer in Redis. Reconnect with jitter and REST recovery. Bounded history and stale-data rejection.
- Celery runs every 900 seconds. PostgreSQL per-symbol transaction locks, idempotent candle keys and persisted Wilder RSI state. Retries cannot duplicate rows. Retention is bounded.
- SQL ranks downward RSI-30 crossings over 24 hours, requires complete consecutive volume windows and >=50% quote-volume growth. Parameterized query, supporting indexes and real EXPLAIN evidence.
- Optional independent identity: Argon2id, short JWTs, hashed opaque refresh tokens, atomic rotation, family revocation on reuse, JWT session validation and shared Redis auth rate limits. Disabled by default. No Supabase account migration.
- Read-only public cached market endpoints with shared rate limiting, bounded response and freshness checks. Browser integration opt-in, fails safely to existing source.
- Unit/API/security and real PostgreSQL/Redis tests. >=85% measured Python coverage, reproducible uv lock, CI, non-root Docker images, health checks and runbook. Never invent passing badges.

Stack: Python 3.12, FastAPI, Celery, Redis 7, PostgreSQL 17, psycopg, PyJWT, argon2-cffi, websockets, httpx.
Layout: src/shepard_engine, tests, sql, docs, .github/workflows.
Style: typed Python functions; parameterized SQL; explicit dependency injection at API boundary.
Commands: uv sync --locked --group dev; uv run pytest; uv run ruff check .; uv run ruff format --check .; docker compose --env-file .env.local up --build -d.
Boundaries: preserve existing application; local isolated infrastructure only; no committed credentials, live exchange orders or paid resources.
Risks: Docker/remote exchange availability; insufficient recovery history must fail explicitly; isolated identity is a learning module, not a replacement for existing production authentication.
