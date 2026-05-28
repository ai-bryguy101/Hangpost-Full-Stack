# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we
> are*. `CLAUDE.md` tracks *what we decided*. ADRs track *why*. Updated
> at the **end** of every session in the same commit as the work.

Last updated: **2026-05-28**
Active branch: `claude/hopeful-volta-ZOBFt` (open as PR #5 → `main`)
Current phase: **Phase 1 ✅ complete — verified end-to-end on docker-compose**

---

## Phase status (mirrors `CLAUDE.md` §6)

| Phase | Status | Notes |
|---|---|---|
| 0. Foundation | ✅ done | Schema, ORM, seed, CI, ADRs 0001–0004. |
| 1. Auth + Profile + Matching | ✅ done | Engine pinned, 1,000 embeddings backfilled, `/recommendations` returns six-tier ranked output with `MatchBreakdown`, impressions logged, Clerk wired, `/demo` page renders results in a browser. End-to-end verified on docker-compose 2026-05-28. |
| 2. Location + Feed MVP | ⏳ blocked | On Figma/Stitch designs (ADR-0005). |
| 3. Matching deepening | ⏳ | Logging seam exists; UI work blocked on Phase 2. |
| 4. Hangouts + Real-time | ⏳ | Not started. |
| 5. Friend graph + Social | ⏳ | Not started. |
| 6. Observability + hardening | ⏳ | Not started. |
| 7. Close the ML loop | ⏳ | Not started. |

---

## What is deployed today

**API (`apps/api`)**

- 1,000 synthetic DC profiles seeded by `python -m hangpost_api.seed` (idempotent, `auth_provider='seed'`).
- All 1,000 profiles have `bio_synthesized` + 384-dim `embedding` (backfilled via `python -m scripts.backfill_embeddings` using `sentence-transformers/all-MiniLM-L6-v2`).
- `hangpost-matching` pinned to commit `94b15fb` of `ai-bryguy101/hangpost-app` (no PyPI release / no tags upstream).
- Routes mounted (in `main.py`):
  - `GET /health`, `GET /health/ready`
  - `GET /me` (Clerk JWT required)
  - `POST /profiles`, `GET /profiles/me`, `PATCH /profiles/me` (Clerk JWT required; embed-on-write)
  - `GET /recommendations` (Clerk JWT or `?source_user_id=…` query param) — `ST_DWithin` pre-filter → load mutual-friend sets → engine `rank_candidates_with_cold_start` → log `recommendation_impressions` → return ranked list with full `MatchBreakdown`.
- Schema: 2 Alembic revisions applied (`0001_initial_schema`, `0002_age_floor_18`). Profile age constraint is 18–120.

**Web (`apps/web`)**

- Homepage with API health status + link to `/demo`.
- `/demo` server-rendered page rendering top-N recommendations with display name, handle, score, tier label, and component-score chips.
- Clerk wired: `clerkMiddleware()`, `<ClerkProvider>`, `SignInButton` / `SignUpButton` / `UserButton` in the header. No pages auth-gated yet.

**Infra**

- `docker-compose` stack: Postgres 16 (PostGIS + pgvector), Redis 7, migrate one-shot, API (CPU-only torch, libgomp1 runtime), Web (Next 15 standalone). Up via `docker compose -f infra/compose/docker-compose.yml up -d --build`.
- CI passes ruff + mypy + pytest + eslint + tsc + vitest + Docker builds. Web build / docker step use a placeholder Clerk publishable key.

---

## What is intentionally NOT done yet

| What | Why | Unblocks |
|---|---|---|
| **No profile-create UI.** After Clerk sign-up the user has a `users` row but no `profiles` row, so `/me` works but `/recommendations` 404s. The seed-corpus path (`/demo?source_user_id=…`) is the demoable surface. | Form needs handle picker, interests/likes chips, and a "use my current location" button — meaningful UI work. | A real signed-in user seeing themselves ranked. |
| **No `POST /user-locations` endpoint.** No way for a Clerk user to set a location, so the radius pre-filter has nothing to filter against. | One-line endpoint, but blocked on the geolocation UI conversation. | Same as above. |
| **`/recommendations` keeps the `source_user_id` query param.** | Drops once a real signed-in user can be the source. Transitional. | Removable after the two items above. |
| **Embed-on-write is inline.** ~50 ms warm, ~2 s cold on first request. Acceptable for one-user dev. | Move to Arq when traffic appears. | Phase 6 hardening. |
| **Email-collision on Clerk upsert = first-write-wins.** Second sub with same email → 500. | Fine for synthetic users. | Before public launch. |
| **No outcome capture.** `recommendation_outcomes` table exists but no endpoints / UI write to it. | Needs the matching UI of Phase 3 to surface "viewed / friended / blocked" actions. | Phase 3 + 7. |
| **No PWA, no posts, no hangouts, no friend graph.** | Phase 2 onward; Phase 2 is blocked on Figma designs (ADR-0005). | Design pipeline. |

---

## Next session — concrete picks

Choose one. Both are useful, neither blocks Phase 2.

1. **Finish the real-user loop (1.5 follow-on).** Build the profile-setup flow: `POST /user-locations` endpoint, `/profile/new` form on the web app, redirect from sign-up → profile setup → `/demo`. Net result: sign up with Clerk, fill out 8 fields, watch yourself get ranked against the 1,000.
2. **Start Phase 2 prep without UI.** Add geolocation helpers (`POST /user-locations` from a browser-side `navigator.geolocation` call), document the PWA manifest, sketch the posterboard data flow. Frontend lands when designs do.

(Pick 1 if the goal is "demoable today end-to-end". Pick 2 if you want momentum on Phase 2 while waiting on Figma.)

---

## External inputs needed

**Operator / Clerk** (to make sign-in actually work in Codespaces — see `docs/CLERK_SETUP.md`):

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (Codespaces secret)
- `CLERK_SECRET_KEY` (Codespaces secret)
- `CLERK_JWKS_URL` (Codespaces secret)

**Sibling repo** (`ai-bryguy101/hangpost-app`): swap the SHA pin for a tag whenever upstream cuts one.

**Design** (Phase 2): Figma library + decision on whether to commit raw Stitch output or hand-translate to shadcn/ui (recommendation in ADR-0005: hand-translate).

---

## Session log

### 2026-05-28 — Phase 1 end-to-end (PR #5)

- 1.1–1.3: engine pinned at `94b15fb`, `apps/api/scripts/backfill_embeddings.py`, `GET /recommendations` with impression logging.
- 1.4–1.6: Clerk JWT verification (`PyJWKClient`), `GET /me`, profile create/edit, embed-on-write.
- Age floor: 13 → 18 (`profiles_age_check` constraint + Alembic `0002`).
- Verified the demo path in Codespaces: 1,000 seeded → 1,000 embedded → `/recommendations` returns top-3 with `semantic_similarity` 0.84–0.88; 10 `recommendation_impressions` rows logged.
- Bugs caught during the verify pass: numpy-float-leak via pgvector → JSONB serializer, missing CPU-torch index (~3 GB CUDA libs filling the disk), seed CSV not shipped in the runtime image.
- Web: `/demo` page + Clerk wiring (`<ClerkProvider>`, middleware, sign-in/up buttons). `docs/CLERK_SETUP.md` runbook.

### 2026-05-28 — Repo assessment + memory infra (pre-Phase-1)

- Phase 0 review; revised Phase 1 sequencing to lead with matching engine instead of Clerk (`docs/DECISIONS_LOG.md`).
- Added `docs/STATUS.md` (this file), `docs/DECISIONS_LOG.md`, ADR-0005 (design pipeline = Figma + Stitch → shadcn/ui).
