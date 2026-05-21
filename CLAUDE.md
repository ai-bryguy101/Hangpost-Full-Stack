# Hangpost App — Project Context (CLAUDE.md)

This file is the persistent context for the **Hangpost app repo**. It's
loaded automatically at the start of every Claude Code session and
captures the product vision, architectural decisions, and operator
environment that must NOT be re-derived or guessed.

The **matching engine** that powers this app lives in a separate repo
(`ai-bryguy101/hangpost-app` — to be renamed `hangpost-matching-engine`).
This app installs it as a pip dependency. Do NOT reimplement matching
logic here.

---

## 1. Operator environment — BROWSER-ONLY

The repo owner operates **entirely through the browser**. No local CLI,
no laptop terminal, no local Python, no local git, no `~/.zshrc` to
edit. Every workflow must execute inside a browser-accessible tool:

- ✅ **GitHub Codespaces** — default for any task that needs a shell.
  Secrets via *Settings → Secrets and variables → Codespaces*.
- ✅ **GitHub.com web UI** — PRs, settings, in-browser file editor.
- ✅ **Vercel / Fly.io / Neon / Upstash web dashboards** — deployments,
  database, Redis.
- ✅ **Claude Code on the web** (this assistant) — code edits.
- ❌ Never suggest `pip install` on the user's laptop,
  `huggingface-cli login` from a local clone, `echo ... >> ~/.zshrc`,
  or any step that assumes a shell on the user's machine.

Default playbook for anything needing a shell: Codespaces → put secrets
in repo Codespaces secrets → run commands in the in-browser terminal →
commit and push from the Codespace.

---

## 2. What we're building

**Hangpost is a location-based social-media app for making new friends
in your current city — the app you download when you move somewhere
new.** It looks like Instagram but every post is location-scoped to
where you are physically right now, and the audience is "nearby
strangers you'd statistically get along with," not "people you already
know."

### Core product surfaces

1. **City posterboard feed** — vertical feed of posts from people
   currently nearby. Two dominant post types: *hangout opportunities*
   ("grabbing drinks at 7, anyone in?") and *local info* ("avoid the
   14 bus 5–6pm").
2. **Matched daily picks** — a small curated set of recommended
   profiles per day, ranked by the matching engine, with a visible
   `MatchBreakdown` explaining *why* each ranked where it did.
3. **Low-lift hangouts** — atomic unit of social action is "post a
   hangout, others tap I'm in" rather than 1:1 cold DMs.

### The radius is a HARD pre-filter, NOT a ranking signal

The single most common point of confusion. Two structurally distinct
location concepts:

- **Current GPS location**: `ST_DWithin` pre-filter at the candidate
  retrieval layer. Profiles outside the radius are removed before the
  ranker runs. **Distance never enters the score.**
- **Hometown**: a soft matching signal, weighted alongside mutual
  friends, college, hobbies, and age.

If anyone proposes `distance_km` as a feature in the ranker, reject it.

### Tier order (matches the matching engine)

1. Mutual friends (friends-of-friends — #1 real-world friendship path)
2. Shared background (hometown + college, peer-strength independent
   signals)
3. Hobbies + interests overlap

---

## 3. Architecture — modular monolith

Single deployable, domain-separated by Python package. Microservices
are a future-state, not a starting point. See `docs/adrs/0001-modular-monolith.md`.

### Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend framework | **Next.js 15 App Router** + React 19 + TypeScript | Industry standard 2026; PWA-capable |
| Styling | **Tailwind v4 + shadcn/ui** | Fast to ship, accessible by default |
| Frontend state | TanStack Query (server) + Zustand (client) | Minimal boilerplate |
| Backend | **FastAPI** + Pydantic v2 + async SQLAlchemy 2.0 | Reuses matching engine in-process; auto OpenAPI |
| Database | **PostgreSQL 16 + PostGIS + pgvector** | Spatial pre-filter; embedding storage native |
| Cache + pub/sub | **Redis 7** | Sessions, rate limits, WebSocket fan-out |
| Auth | **Clerk** (free tier) | Production-grade in an hour |
| Object storage | **Cloudflare R2** | S3-compatible, ~10× cheaper egress |
| Background jobs | **Arq** | Async-native, Redis-backed, tiny |
| Real-time | FastAPI WebSockets + Redis pub/sub | Native, horizontal scaling via Redis |
| Hosting (web) | **Vercel** | Free hobby tier, zero-config Next.js |
| Hosting (api) | **Fly.io** | Cheap, regional, Dockerfile-based |
| Managed DB | **Neon** | PostGIS + pgvector + free tier |
| Observability | **OpenTelemetry → Grafana Cloud** + **Sentry** | Vendor-neutral traces, free tiers |
| CI/CD | **GitHub Actions** | PR previews + main → staging → prod |

### Repo layout

```
hangpost-app/
  apps/
    api/                  ← FastAPI service
      src/hangpost_api/
        auth/  profiles/  posts/  hangouts/  matching/  notifications/
        safety/  recommendations/  workers/
      alembic/  tests/
    web/                  ← Next.js 15 + shadcn/ui
      src/app/  src/components/  src/lib/
  packages/
    shared-types/         ← OpenAPI-generated TS client
  infra/
    docker/  compose/
  docs/
    adrs/  ARCHITECTURE.md  RUNBOOK.md  SCHEMA.sql
  .github/workflows/
```

---

## 4. Domain model

Full DDL in `docs/SCHEMA.sql` (generated from this plan). Key tables:

- **`users`** — auth provider + sub.
- **`profiles`** — structured fields matching `hangpost_matching.UserProfile`,
  plus `embedding vector(384)` (pgvector, HNSW indexed) and
  `bio_synthesized` (output of `profile_to_text()`).
- **`user_locations`** — `geography(POINT, 4326)`, GIST indexed. Source
  of truth for the radius pre-filter.
- **`posts`** — `type` (hangout | local_info), `visibility` (matched
  only | friends-of-friends | public-in-area), `posted_geom`,
  `radius_m`. GIST-indexed.
- **`hangouts`** + **`hangout_rsvps`** — one-to-many with posts.
- **`friendships`** — pending/accepted/blocked edges.
- **`friendship_imports`** — provenance + `consent_hash` for GDPR.
- **`recommendation_impressions`** — every recommendation surfaced,
  with `score`, `model_version`, full `breakdown_json`. Logs the ranker
  in production.
- **`recommendation_outcomes`** — `viewed`, `profile_opened`,
  `friend_request_sent`, `blocked`, `hangout_rsvped`. Joins to
  impressions by id.
- **`user_blocks`** + **`reports`** — first-class safety.
- **`notifications`** — partial index on unread for cheap inbox queries.

---

## 5. The ML loop — closing it

The matching engine in the sibling repo trains on synthetic labels and
LLM-judge labels today. The app's job is to replace those with **real
outcome data**:

```
FastAPI → hangpost_matching.rank() → log impression →
  → user action → log outcome → nightly Arq worker →
  → LearnedRanker.fit(queries) → S3 model registry →
  → A/B against current champion → hot-swap if better
```

The matching engine doesn't need to change — `LearnedRanker` already
accepts a `Query` iterable. This is the headline "I shipped real-world
ML" story. Build the logging from Phase 3 (matching integration); the
weekly retraining job is Phase 7.

---

## 6. Build phases

| Phase | Outcome |
|---|---|
| 0. Foundation | Codespaces + docker-compose stack runs; Alembic migrations apply; CI green |
| 1. Auth + Profile | Clerk integrated; profile create/edit; embedding writes to pgvector |
| 2. Location + Feed MVP | PWA geolocation; PostGIS radius query; posterboard UI |
| 3. Matching integration | `/recommendations` endpoint; impression logging; `MatchBreakdown` UI |
| 4. Hangouts + Real-time | RSVP flow; WebSocket notifications via Redis pub/sub |
| 5. Friend graph + Social | Friend requests; contact import with consent; blocks; reports |
| 6. Observability + hardening | OTel traces; Sentry; rate limiting; CSP; load test |
| 7. Close the ML loop | Outcome ETL; weekly retrain; model registry; A/B harness |

Each phase ends in a deployable, demoable increment.

---

## 7. CI/CD baseline (Phase 0)

Three GitHub Actions workflows:

- **PR**: ruff + mypy + eslint + tsc + pytest + vitest + docker build +
  Trivy scan + spin up preview env on Fly.io + Playwright smoke.
- **main → staging → prod**: tag-based, manual approval gate before
  prod, blue/green via `fly deploy --strategy bluegreen`.
- **nightly**: re-run offline evaluation on last 7 days of outcomes; if
  candidate beats champion by ≥2% NDCG, open auto-PR with new model.

---

## 8. Senior judgment — explicitly defer

- No Kubernetes. Fly.io is production-grade.
- No microservices. Modular monolith first.
- No GraphQL. REST + OpenAPI codegen ships faster.
- No event sourcing / CQRS.
- No Neo4j. Postgres handles the friend graph at this scale.
- No React Native day 1. PWA first.
- No custom auth. Clerk → Supabase Auth migration path documented.

---

## 9. Code style + AI session preferences

- TypeScript strict mode. No `any`. No `@ts-ignore`.
- Python: ruff + mypy strict, 100 char lines, beginner-friendly
  docstrings (this is also a learning project for the operator).
- Conventional commits. PRs squash-merged. Branch off `main` with
  descriptive names; `claude/<session-id>` only for AI-driven sessions.
- ADRs for any decision worth defending: `docs/adrs/NNNN-title.md`.
- Default to NO comments unless WHY is non-obvious. Never narrate
  WHAT.
- Always ground decisions in this file. If something here is wrong,
  open an ADR proposing the change before changing code.

---

## 10. Resume context

This repo is a portfolio piece for senior AI / full-stack engineer
roles. The pitch is *"I designed and shipped a real social product
with a recommendation engine I built, evaluated, and distilled myself.
The data model, services, deployment, and CI/CD are production-grade.
I closed the ML loop by feeding live outcomes back into the ranker."*

Every PR should reinforce that story. If a change doesn't make the
pitch stronger or fix a real bug, postpone it.

---

## 11. Reference

- Matching engine repo: <https://github.com/ai-bryguy101/hangpost-app>
- Matching engine PyPI: `pip install hangpost-matching` (when published)
- Product vision (long-form): `docs/PRODUCT_VISION.md` (port from sibling repo)
- This file is `CLAUDE.md` and lives at the repo root.
