# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we
> are*. `CLAUDE.md` tracks *what we decided*. ADRs track *why*. Updated
> at the **end** of every session in the same commit as the work.

Last updated: **2026-05-29**
Active branch: `claude/nifty-lamport-12eR7` (PR B — close the ML loop)
Current phase: **Phase 1 ✅ + real-user loop (PR A, merged) + ML loop closed (PR B)**
PR A merged as #7 — and with it `main`'s CI went green for the first
time (it had been red since #5 on a stale `type: ignore` + a malformed
CI Clerk placeholder key, both fixed in #7).
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
  - `POST /user-locations` (Clerk JWT required) — upserts the caller's `user_locations` row from a browser `navigator.geolocation` fix (EWKT `SRID=4326;POINT(lon lat)`, same format as the seed path). Lives in the `profiles` package (`profiles/locations.py`) since that package owns the table.
  - `GET /recommendations` (**Clerk JWT only** — the `source_user_id` query-param fallback was retired) — `ST_DWithin` pre-filter → load mutual-friend sets → engine `rank_candidates_with_cold_start` → log `recommendation_impressions` (now with an `impression_id` per result in the response **and** a `features_json` raw-input snapshot per row) → return the ranked list with full `MatchBreakdown`.
  - `POST /recommendations/{impression_id}/outcomes` (Clerk JWT required) — records a training label (`action` ∈ viewed/profile_opened/friend_request_sent/blocked/hangout_rsvped) by upserting `recommendation_outcomes`. Idempotent + additive (actions accumulate on one row); ownership-checked (404 if the impression isn't the caller's).
- Schema: 3 Alembic revisions applied (`0001_initial_schema`, `0002_age_floor_18`, `0003_impression_features_json`). Profile age constraint is 18–120.

**Web (`apps/web`)**

- Homepage with API health status + link to `/demo`.
- `/profile/new` client form (display name, handle, age, hometown, college, interests, liked_topics) with a **"Use my current location"** button that calls `navigator.geolocation` → `POST /user-locations`. Submit is gated on location being set (so landing on `/demo` can't 409), POSTs `/profiles`, then redirects to `/demo`. A 409 (profile already exists) redirects to `/demo` instead of erroring.
- `/demo` server-rendered page rendering top-N recommendations (**Clerk-JWT-only** now). A signed-in user with no profile (404) or no location (409) gets an onboarding CTA to `/profile/new` instead of a raw error. Cards live in a `"use client"` `RecommendationList` that **captures outcomes**: `viewed` fires once per card on mount, clicking a name fires `profile_opened`, "Add friend" fires `friend_request_sent`; "Dismiss" hides a card client-side only (no DB write — see DECISIONS_LOG on not faking a `blocked` label).
- Clerk wired: `clerkMiddleware()`, `<ClerkProvider>`, `SignInButton` / `SignUpButton` / `UserButton`. **Sign-up redirects to `/profile/new`** (`forceRedirectUrl`).
- `lib/api.ts` shared typed `apiFetch` seam + `ApiError`; `createProfile` / `postUserLocation` / `postOutcome` route through it.

**Infra**

- `docker-compose` stack: Postgres 16 (PostGIS + pgvector), Redis 7, migrate one-shot, API (CPU-only torch, libgomp1 runtime), Web (Next 15 standalone). Up via `docker compose -f infra/compose/docker-compose.yml up -d --build`.
- CI passes ruff + mypy + pytest + eslint + tsc + vitest + Docker builds. Web build / docker step use a placeholder Clerk publishable key.

---

## What is intentionally NOT done yet

| What | Why | Unblocks |
|---|---|---|
| **Real-user demo loop not yet verified against live Clerk.** PR A shipped the code (`/profile/new` form, `POST /user-locations`, JWT-only `/recommendations`, sign-up redirect) but it has only been exercised by unit/smoke tests + CI — the end-to-end click-through needs the Clerk Codespaces secrets set (see "External inputs needed"). | Operator action: set the three Clerk secrets, then walk sign-up → `/profile/new` → `/demo`. | A recruiter clicking through the live demo. |
| **Embed-on-write is inline.** ~50 ms warm, ~2 s cold on first request. Acceptable for one-user dev. | Move to Arq when traffic appears. | Phase 6 hardening. |
| **Email-collision on Clerk upsert = first-write-wins.** Second sub with same email → 500. | Fine for synthetic users. | Before public launch. |
| **No outcome capture.** `recommendation_outcomes` table exists but no endpoints / UI write to it. | Needs the matching UI of Phase 3 to surface "viewed / friended / blocked" actions. | Phase 3 + 7. |
| **No PWA, no posts, no hangouts, no friend graph.** | Phase 2 onward; Phase 2 is blocked on Figma designs (ADR-0005). | Design pipeline. |

---

## Next session — concrete picks

Three small PRs queued, in resume-impact order. Each is one session,
each is demoable on its own, none blocks Phase 2.

### PR A — Real-user demo loop ✅ DONE (branch `claude/nifty-lamport-12eR7`)
**Goal:** a recruiter can sign up and watch themselves get ranked
against the 1,000 synthetic Washingtonians in 30 seconds.
- ✅ `POST /user-locations` endpoint (browser `navigator.geolocation`
  output → `user_locations`; in `profiles/locations.py`).
- ✅ `/profile/new` form (display name, handle, age, hometown, college,
  interests, liked_topics, "use my current location"). Location is
  required before submit so `/demo` can't 409.
- ✅ Sign-up redirects to `/profile/new` (`forceRedirectUrl`),
  then `/demo` after profile creation.
- ✅ Dropped the `source_user_id` optional-auth fallback — `/recommendations`
  is Clerk-JWT-only. `/demo` is sign-in-gated.
- Remaining: live-Clerk click-through verification (needs the Codespaces
  secrets). Next up is **PR B**.

### PR B — Close the ML loop ✅ DONE (branch `claude/nifty-lamport-12eR7`)
**Goal:** the system not only *recommends* but also *measures whether
the recommendation was good* — the headline AI-engineering story.
- ✅ `POST /recommendations/{impression_id}/outcomes` (action ∈ {viewed,
  profile_opened, friend_request_sent, blocked, hangout_rsvped}); upserts
  `recommendation_outcomes`, idempotent + additive, ownership-checked.
- ✅ `/demo` outcome capture via the `RecommendationList` client component:
  `viewed` on mount, `profile_opened` on name click, `friend_request_sent`
  on "Add friend". (Swapped the planned "not interested"→`blocked` for a
  clean positive signal + a client-only Dismiss — see DECISIONS_LOG.)
- ✅ `scripts/evaluate.py` + pure stdlib `recommendations/evaluation.py`:
  NDCG@10 + Recall@10 for the live ranker vs. popularity + random
  baselines, grouped by query, written to `docs/eval/`. Metrics
  unit-tested (`tests/test_evaluation.py`); a synthetic self-test report
  is committed (`docs/eval/SYNTHETIC-self-test.md`) — the first **real**
  report is a Codespaces step once outcomes accrue.
- ✅ Feature snapshot: `recommendation_impressions.features_json` (new,
  nullable; Alembic `0003`) logs the raw ranker inputs per impression so
  Phase 7 can replay history without feature-skew. `impression_id` is now
  in the GET response so the client can POST outcomes.

### PR C — Observable and presentable  ← **next**
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

### 2026-05-29 — PR B: close the ML loop (branch `claude/nifty-lamport-12eR7`)

- **Outcome capture**: `POST /recommendations/{impression_id}/outcomes`
  (idempotent + additive upsert, ownership-checked); `OutcomeAction`
  enum + `OutcomeCreate`/`OutcomeRead` schemas. GET now returns an
  `impression_id` per result (generated in Python, not via bulk-insert
  RETURNING) so the client can post against it.
- **Feature snapshot**: new nullable `recommendation_impressions.features_json`
  (Alembic `0003` + SCHEMA.sql) logging raw ranker inputs per impression;
  batch `surfaced_at` pinned in Python so the evaluator can group
  impressions into queries deterministically.
- **Offline eval**: pure-stdlib `recommendations/evaluation.py` (NDCG@10 /
  Recall@10 + graded relevance + popularity/random baselines), unit-tested;
  thin DB driver `scripts/evaluate.py` writes a markdown report to
  `docs/eval/`. Committed `docs/eval/README.md` + a clearly-labeled
  `SYNTHETIC-self-test.md` generated by the real module (synthetic inputs,
  real math: live 0.93 vs popularity 0.58 vs random 0.57 NDCG@10). The
  first real report is a Codespaces step once outcomes exist.
- **Web**: extracted `/demo` cards into a `"use client"` `RecommendationList`
  that fires `viewed`/`profile_opened`/`friend_request_sent`; `postOutcome`
  added to `lib/api.ts`; vitest added.
- **Decision** (DECISIONS_LOG): dropped the planned "not interested"→`blocked`
  mapping (nothing reads `outcomes.blocked`; conflating it with the
  `user_blocks` safety table is dishonest) in favour of a positive
  `friend_request_sent` signal + a client-only Dismiss.
- **Verification**: ruff + py_compile + the synthetic eval run locally;
  mypy/pytest/eslint/tsc/vitest/build run in CI (npm + PyPI blocked here).
- Refreshed `docs/CLERK_SETUP.md` §6 (profile auto-creation now exists;
  noted the DC-seed-corpus geolocation/radius caveat).

### 2026-05-29 — PR A: real-user demo loop (branch `claude/nifty-lamport-12eR7`)

- Confirmed the replan still holds (no work started on PRs A/B/C, no open
  PRs, trees clean) before starting.
- **API**: new `POST /user-locations` (upsert, Clerk-auth, EWKT geom
  mirroring `seed.py`) in `profiles/locations.py`; `GET /recommendations`
  made Clerk-JWT-only (dropped the `source_user_id` query param + the
  400 branch); auth smoke tests updated (recommendations now 401 without
  a token; added a no-token test for `/user-locations`).
- **Web**: `/profile/new` client form + "use my current location" button;
  sign-up redirects to it (`forceRedirectUrl`); `/demo` is now
  JWT-only and shows an onboarding CTA on 404/409; `lib/api.ts` gained a
  shared `apiFetch`/`ApiError` seam reused by `createProfile` /
  `postUserLocation`; vitest added for the new helpers.
- **Decision applied** (DECISIONS_LOG): require a location before the
  profile-form submit so a fresh user never lands on a 409'd `/demo`;
  fold the location endpoint into the `profiles` package rather than a
  new top-level package.
- **Verification note**: this remote environment's network policy blocks
  npm + PyPI, so only `ruff` + `py_compile` ran locally (both pass). The
  web gates (tsc/eslint/vitest) and `pytest` run in CI on push.

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
