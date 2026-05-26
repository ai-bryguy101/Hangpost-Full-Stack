# Hangpost

**A location-based social app for making new friends in your current
city — the app you download when you move somewhere new.** It looks like
Instagram, but every post is scoped to where you physically are right
now, and the audience is "nearby strangers you'd statistically get along
with," ranked by a matching engine built and evaluated in a sibling repo.

## Monorepo layout

```
apps/api      FastAPI service (modular monolith) + Alembic migrations
apps/web      Next.js 15 App Router + Tailwind v4 frontend (PWA)
packages/     shared-types (OpenAPI-generated TS client — Phase 1)
infra/        Dockerfiles + docker-compose (local stack)
docs/         ADRs, ARCHITECTURE.md, RUNBOOK.md, SCHEMA.sql
.github/      CI workflows
```

## Quick start

```
docker compose -f infra/compose/docker-compose.yml up --build
```

- API:  http://localhost:8000  (`/docs`, `/health`)
- Web:  http://localhost:3000

Migrations apply automatically before the API starts. See
`docs/RUNBOOK.md` for non-Docker setup and day-to-day operations.

## Where to read next

- `CLAUDE.md` — product vision, architecture decisions, build phases.
- `docs/ARCHITECTURE.md` — code layout and request flow.
- `docs/adrs/` — the decisions worth defending.
- `Hangpost Full-Stack Build Plan.md` — the long-form plan.

## Status

Phase 0 (Foundation): scaffolding, schema migrations, local stack, and CI
are in place. Subsequent phases (auth, feed, matching integration,
real-time, social graph, observability, ML loop) follow the plan in
`CLAUDE.md` §6.

The matching engine lives in a separate repo and is installed as a pip
dependency — it is **not** reimplemented here.
