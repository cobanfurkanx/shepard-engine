# Shepard Engine

[![Engine CI](https://github.com/cobanfurkanx/shepard-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/cobanfurkanx/shepard-engine/actions/workflows/ci.yml)
[![Local branch coverage 96.15%](https://img.shields.io/badge/local_branch_coverage-96.15%25-brightgreen)](docs/VALIDATION.md)

Independent public-market backend for [Shepard AI](https://github.com/cobanfurkanx/shepardai-crypto-advisor). No live orders. Existing Supabase Auth, billing and app analysis remain unchanged.

```mermaid
flowchart LR
  Binance[Binance public WebSocket / REST recovery] --> Redis[Redis cache / bounded candle history]
  Redis --> Worker[Celery worker]
  Beat[Celery Beat: every 15 minutes] --> Worker
  Worker --> PG[Isolated PostgreSQL / persisted Wilder RSI state]
  PG --> API[FastAPI read-only market reports]
  Redis --> API
  API --> Scanner[Optional scanner / disabled by default]
  Demo[Optional JWT identity demo] --> PG
  App[Existing Shepard app] --> Supabase[Existing Supabase Auth / billing / analysis]
```

## Run locally

Python 3.12, uv 0.12.5 and Docker Desktop are required. On Windows move Docker's disk image to D before pulling images if C is constrained. Celery runs inside Linux containers.

```powershell
uv sync --locked --group dev
uv run python scripts/init_local.py
docker compose --env-file .env.local --profile engine up --build -d
```

The ignored `.env.local` is the engine's shared configuration. `init_local.py` generates random credentials and refuses to overwrite an existing file. The app keeps its own configuration. PostgreSQL/Redis volumes survive restarts.

API: `http://localhost:58080/docs`. Infrastructure readiness: `/health/ready`. Data-flow readiness: `/health/market` (may be unavailable during warm-up).

Once ingestion is connected, request the initial job instead of waiting for the next 15-minute tick:

```powershell
docker compose --env-file .env.local exec -T worker celery -A shepard_engine.worker:app call engine.persist_market
```

## Verify

```powershell
uv run python scripts/init_test_database.py
$env:RUN_INTEGRATION='1'
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
```

Integration tests use the separate `engine_test` database and Redis DB 15. They refuse other database names. The default coverage gate is **85%**, including branches and all engine modules. A suite without infrastructure intentionally cannot satisfy that gate.

GitHub Actions workflow: `.github/workflows/ci.yml`. Before enabling it, configure `CI_DB_PASSWORD` as an Actions secret (random URL-safe hex). A GitHub passing badge is added only after the repository exists and its workflow succeeds; local test evidence is in [VALIDATION.md](docs/VALIDATION.md).

## API

| Route | Purpose |
|---|---|
| `GET /health/live` | Process liveness |
| `GET /health/ready` | PostgreSQL and Redis readiness |
| `GET /health/market` | Ingestion and worker freshness |
| `GET /v1/market/ticker/{symbol}` | Fresh allowlisted ticker, or 503 |
| `GET /v1/market/top-coins` | Up to five RSI-crossing / volume-growth matches |
| `POST /v1/auth/register`, `/login`, `/refresh`, `/logout` | Optional independent identity demo |
| `GET /v1/auth/me` | JWT and active-session protected user endpoint |

The report counts transitions from RSI >=30 to <30 over the latest complete 24-hour window. Quote volume must grow >=50% relative to the previous complete window. Both windows require 96 distinct closed 15m candles. This is descriptive analytics, not a buy/sell recommendation. An empty result is valid.

## Identity boundary

`ENGINE_IDENTITY_ENABLED=false` by default. To run isolated auth tests or demos, enable it and supply a random `ENGINE_JWT_SECRET` of at least 32 characters. Passwords use Argon2id; refresh tokens are random and stored as SHA-256 hashes. JWTs expire within 15 minutes and refresh families within seven days. Rotation uses PostgreSQL row locks; reuse commits family revocation before returning 401, invalidating access tokens too.

Concurrent use of the same refresh token is treated as reuse: exactly one rotation wins and the resulting family is then revoked. Clients must serialize refresh requests and require a fresh login after lost/replayed refresh responses. This deliberate strict policy is covered by concurrency tests.

Tokens are returned as JSON for API demonstration. This module does not implement browser cookie sessions, email verification, password reset or Supabase migration; keep app authentication on Supabase.

## Operations and boundaries

See [OPERATIONS.md](docs/OPERATIONS.md), [query-plan evidence](docs/QUERY_PLAN.md) and [source references](docs/SOURCES.md). Compose exposes ports only on localhost, uses non-root read-only engine containers, resource limits, persistent volumes and Redis authentication. It is a local deployment definition; internet hosting needs a TLS gateway, trusted-proxy policy, backups and a separate runtime DB role.

The optional app scanner is behind `VITE_ENABLE_ENGINE_SCANNER=false`. Enabling it requires an explicit HTTPS engine URL (localhost accepted for development) and matching CORS origin. It sends no Supabase JWT or cookies. Supabase usage limits remain applicable to existing app features.
