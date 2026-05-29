# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we
> are*. `CLAUDE.md` tracks *what we decided*. ADRs track *why*. Updated
> at the **end** of every session in the same commit as the work.

Last updated: **2026-05-29**
Active branch: `claude/gifted-dirac-bjTLc` (post-PR-#5; assessment-only session, no code change)
Current phase: **Phase 1 ✅ complete — verified end-to-end on docker-compose**
Resume framing (CLAUDE.md §10): every next PR must strengthen the
"I shipped a recommender, evaluated it, and closed the loop on real
outcomes" pitch. If a change doesn't, postpone it.

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

Three small PRs queued, in resume-impact order. Each is one session,
each is demoable on its own, none blocks Phase 2.

### PR A — Real-user demo loop (the 1.5 follow-on)
**Goal:** a recruiter can sign up and watch themselves get ranked
against the 1,000 synthetic Washingtonians in 30 seconds.
- `POST /user-locations` endpoint (takes browser `navigator.geolocation`
  output, writes to `user_locations`).
- `/profile/new` form on the web (display name, handle, age, hometown,
  college, interests, liked_topics, "use my current location").
- After Clerk sign-up, redirect new users to `/profile/new`, then to
  `/demo` (no `?source_user_id=…` query param needed once a real user
  can be the source).
- Drop the optional-auth fallback on `/recommendations`.

### PR B — Close the ML loop (Phase 3 + 7 seam, pulled forward)
**Goal:** the system not only *recommends* but also *measures whether
the recommendation was good*. This is the headline AI-engineering
story; bringing even a thin version forward now strengthens every
recruiter conversation.
- Endpoint: `POST /recommendations/{impression_id}/outcomes`
  (action ∈ {viewed, profile_opened, friend_request_sent, blocked,
  hangout_rsvped}). Table already exists (`recommendation_outcomes`),
  nothing writes to it today.
- Three click handlers on the `/demo` cards that POST outcomes
  (mark-viewed on view, profile-open on click, "not interested" on
  dismiss).
- `apps/api/scripts/evaluate.py`: pull last N days of
  impressions+outcomes, compute NDCG@10 + Recall@10 for the current
  ranker vs. a random baseline and a popularity-only baseline, write a
  markdown report to `docs/eval/`. Even one report committed beats no
  measurement story.
- Feature snapshot: also log the raw inputs into the ranker on each
  impression (embedding hash, mutual-friend count, hometown bool, etc.)
  so the offline trainer can replay history when Phase 7 lands.

### PR C — Observable and presentable
**Goal:** the repo *reads* as well as it *runs*. Smallest PR but the
one a recruiter sees first.
- Wire Sentry on browser + API (5-minute job).
- Structured log line per ranker call: `model_version`, latency,
  candidate count.
- Rewrite the README to lead with: one `/demo` screenshot, one
  paragraph on the ML pitch, then the technical detail.
- Cut a tag on the sibling matching-engine repo and swap the SHA pin.
- Fix the email-collision-on-Clerk-signup 500 (first-write-wins).
- Add an integration test for `/recommendations` (boot a tiny seed
  corpus, assert sorted result + valid `MatchBreakdown` shape).
- Add `docs/PRIVACY.md` covering `user_locations` retention.

Phase 2 (posts + feed) stays correctly blocked on Figma designs
(ADR-0005). The three PRs above all unblock independently of design
and all make the resume pitch stronger today.

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

### 2026-05-29 — Post-Phase-1 assessment + resume-lens replan (no code)

- Re-read repo on `claude/gifted-dirac-bjTLc` after PR #5 merged. Phase 1
  state confirmed as in §"What is deployed today"; nothing rotted.
- Operator goal restated: this repo goes on a resume for an AI
  engineer role. Re-ordered the next-steps queue (above) by
  ML-narrative impact rather than by phase number, while keeping the
  CLAUDE.md §6 destination unchanged.
- Decision: bring the *outcome-capture half* of Phases 3 + 7 forward
  into PR B, because the headline pitch in CLAUDE.md §10 (close the
  ML loop on real outcomes) is the single biggest gap a recruiter
  would notice today. The full retraining job stays in Phase 7.
- Decision: keep Phase 2 (posts + feed) blocked on Figma per ADR-0005.
  PRs A/B/C above all ship independently of design.
- Improvements catalogued (offline eval harness, feature snapshots in
  impressions, Sentry-first observability, sibling-repo tag swap,
  README rewrite for recruiter audience, integration test for
  `/recommendations`, `docs/PRIVACY.md` on location retention).

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
