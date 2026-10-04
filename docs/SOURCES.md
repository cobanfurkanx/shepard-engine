# Primary references

- [Binance market-data-only endpoints](https://github.com/binance/binance-spot-api-docs/blob/master/faqs/market_data_only.md): public port-443 streams and REST recovery.
- [Binance WebSocket streams](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md): combined streams, ticker and closed-kline fields, reconnect lifecycle.
- [Celery task delivery and retries](https://docs.celeryq.dev/en/stable/userguide/tasks.html): acknowledge after processing only with idempotency; JSON task serialization and bounded retries.
- [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html): transaction-scoped advisory and row locks.
- [FastAPI JWT example](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/): dependency-based bearer validation and password hashing.
- [Docker Desktop WSL storage](https://docs.docker.com/desktop/features/wsl/): moving engine data via Resources / Advanced.

References guide implementation. Tests verify the concrete contracts; they do not certify production readiness.
