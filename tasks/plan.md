# Implementation order
1. Prove indicator and stream validation contracts with unit tests.
2. Cache/recovery pipeline and idempotent PostgreSQL worker; integration test with Redis and PostgreSQL.
3. Standalone identity with reuse/concurrency tests.
4. SQL report, API, freshness/rate limits, query plan.
5. Compose, CI, dependencies, runbook and measured coverage.
6. Disabled app integration; existing app regression checks.
