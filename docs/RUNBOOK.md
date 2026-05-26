# Hangpost Runbook

Operational playbook. The operator works **browser-only** (CLAUDE.md §1):
GitHub Codespaces for any shell, web dashboards for everything else.

## Local / Codespaces dev

Bring up the whole stack (Postgres+PostGIS+pgvector, Redis, API, web):

```
docker compose -f infra/compose/docker-compose.yml up --build
```

- API:  http://localhost:8000  (docs at `/docs`, health at `/health`)
- Web:  http://localhost:3000
- The `migrate` service runs `alembic upgrade head` before the API starts.

Tear down (keep data): `docker compose -f infra/compose/docker-compose.yml down`
Wipe the database too: add `-v` to remove the `pgdata` volume.

## API without Docker

```
cd apps/api
pip install -e ".[dev]"
alembic upgrade head          # needs a reachable Postgres (see DATABASE_URL)
uvicorn hangpost_api.main:app --reload
```

## Migrations

```
cd apps/api
alembic upgrade head          # apply
alembic downgrade -1          # roll back one
alembic revision -m "msg"     # new revision (hand-edit spatial/vector DDL — ADR 0003)
alembic upgrade head --sql    # emit SQL without applying (offline)
```

After any schema change, update **both** the migration and
`docs/SCHEMA.sql`.

## Configuration

All settings come from the environment via `hangpost_api.core.config`.
See `.env.example` for the full list. Required for the API:

- `DATABASE_URL` — `postgresql+asyncpg://user:pass@host:5432/db`
- `REDIS_URL` — `redis://host:6379/0`

Secrets live in Codespaces secrets / Vercel / Fly dashboards — never in
the repo, never logged.

## CI

`.github/workflows/pr.yml` runs on every PR and on push to `main`:
ruff + mypy + pytest (API), eslint + tsc + vitest + build (web), Docker
builds for both images, and a Trivy filesystem scan. Staging/prod deploy
pipelines and the nightly retrain land in later phases (CLAUDE.md §7).

## Health checks

- `GET /health` — liveness, touches nothing.
- `GET /health/ready` — readiness, runs `SELECT 1` against Postgres.

## Common issues

- **`vector`/`postgis` type unknown on migrate** — the extension was not
  created. The initial migration runs `CREATE EXTENSION` for pgcrypto,
  citext, postgis, and vector; ensure migrations actually ran (the
  `migrate` compose service must complete successfully).
- **API can't reach DB in compose** — confirm `db` is healthy
  (`pg_isready`); the API depends on the db healthcheck and the migrate
  job completing.
