# Security policy

## Supported scope

Security fixes target the current `main` branch. This repository is a local market-data service and an optional identity reference implementation. It does not place trades or host the Shepard AI application's user accounts.

## Deployment boundaries

- Keep PostgreSQL, Redis and the API on loopback as configured by Compose.
- Generate credentials with `scripts/init_local.py`; never commit `.env.local`, real keys, user exports or database backups.
- The JWT identity demo is disabled by default. It is not a complete browser account system.
- Internet deployment requires TLS, reviewed proxy configuration, backups and a dedicated least-privilege runtime database role. See [operations](docs/OPERATIONS.md).
- CI credentials are disposable and only used with isolated test services; they are not production secrets.

## Reporting

Report suspected vulnerabilities privately to `furkancobanbusiness@gmail.com`. Include the affected commit, source path, impact and a minimal reproduction using dummy data. Do not post credentials, user records or exploit details in public issues. No response-time guarantee or paid bounty is offered.
