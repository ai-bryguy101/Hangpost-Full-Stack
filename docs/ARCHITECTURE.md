# Hangpost Architecture

> Companion to `CLAUDE.md` (product + decisions) and the ADRs in
> `docs/adrs/`. This document describes how the code is laid out and how
> a request flows through it.

## Shape

A **modular monolith** (ADR 0001). One FastAPI service, one Next.js
frontend, one Postgres, one Redis. Domains are Python packages with
service-layer boundaries, not separate deployables.

```
apps/
  api/                         FastAPI service
    src/hangpost_api/
      core/                    config, db, enums, logging (no domain imports)
      auth/                    users
      profiles/                profiles + current location
      posts/                   posterboard posts + media
      hangouts/                hangouts + RSVPs
      social/                  friendships + import provenance
      safety/                  blocks + reports
      notifications/           inbox
      recommendations/         impression + outcome logs (the ML loop)
      matching/                thin adapter over the hangpost-matching package
      workers/                 Arq background jobs
      models.py                aggregate import of all ORM models
      main.py                  app shell, middleware, health checks
    alembic/                   migrations (hand-written — ADR 0003)
    tests/
  web/                         Next.js 15 App Router + Tailwind v4
    src/app/                   routes
    src/lib/                   API client (typed client generated in Phase 1)
packages/
  shared-types/                OpenAPI-generated TS client (Phase 1)
infra/
  docker/                      api.Dockerfile, web.Dockerfile (multi-stage)
  compose/                     docker-compose.yml — full local stack
docs/
  adrs/  ARCHITECTURE.md  RUNBOOK.md  SCHEMA.sql
.github/workflows/             CI
```

## Request flow

```
Browser (Next.js, Vercel)
   │  HTTPS, JWT in httpOnly cookie
   ▼
FastAPI (Fly.io)
   │  request-id middleware → structured JSON log line per request
   ├── domain routers → service layer → SQLAlchemy (async) → Postgres
   ├── Redis: sessions, rate limits, WebSocket pub/sub
   └── matching/: builds Query objects → hangpost_matching.rank()
                  → recommendations/: log impression → (user action) → log outcome
```

## Data model

The full schema is `docs/SCHEMA.sql`, realized by the initial Alembic
migration. Highlights:

- `user_locations.geom` (`geography(POINT,4326)`, GIST) — the radius
  pre-filter source of truth (ADR 0004).
- `profiles.embedding` (`vector(384)`, HNSW) — matching engine input.
- `recommendation_impressions` + `recommendation_outcomes` — every ranked
  candidate and its downstream action; the training set that closes the
  ML loop (CLAUDE.md §5).

## The ML loop

`FastAPI → hangpost_matching.rank() → log impression → user action → log
outcome → nightly Arq ETL → LearnedRanker.fit() → model registry → A/B →
hot-swap`. The matching engine is unchanged; the app produces the `Query`
objects its `fit()` already accepts.

## Observability (from day one)

Every request carries an `X-Request-ID` (generated if absent) bound into
a structured JSON log line. OTel spans, Sentry, and the Grafana dashboard
land in Phase 6; the request-id seam exists now so traces have an anchor.

## What is deliberately deferred

Kubernetes, microservices, GraphQL, event sourcing, Neo4j, custom auth,
React Native — see CLAUDE.md §8 and the "what I'd skip" section of the
build plan. Each is a known later step, not a v1 gap.
