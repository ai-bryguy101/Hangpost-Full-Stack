# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we
> are*. `CLAUDE.md` tracks *what we decided*. ADRs track *why*. Updated
> at the **end** of every session in the same commit as the work.

Last updated: **2026-05-30**
Active branch: `claude/gifted-dirac-kE49j` (assessment session — no code, memory only)
Open PR: **#8** (`claude/nifty-lamport-12eR7`) — **PR B: close the ML loop**, awaiting review/merge.
Current phase: **Phase 1 ✅ complete + real-user onboarding loop shipped; PR B in flight**
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
  - `GET /recommendations` (**Clerk JWT only** — the `source_user_id` query-param fallback was retired) — `ST_DWithin` pre-filter → load mutual-friend sets → engine `rank_candidates_with_cold_start` → log `recommendation_impressions` → return ranked list with full `MatchBreakdown`.
- Schema: 2 Alembic revisions applied (`0001_initial_schema`, `0002_age_floor_18`). Profile age constraint is 18–120.

**Web (`apps/web`)**

- Homepage with API health status + link to `/demo`.
- `/profile/new` client form (display name, handle, age, hometown, college, interests, liked_topics) with a **"Use my current location"** button that calls `navigator.geolocation` → `POST /user-locations`. Submit is gated on location being set (so landing on `/demo` can't 409), POSTs `/profiles`, then redirects to `/demo`. A 409 (profile already exists) redirects to `/demo` instead of erroring.
- `/demo` server-rendered page rendering top-N recommendations (**Clerk-JWT-only** now). A signed-in user with no profile (404) or no location (409) gets an onboarding CTA to `/profile/new` instead of a raw error.
- Clerk wired: `clerkMiddleware()`, `<ClerkProvider>`, `SignInButton` / `SignUpButton` / `UserButton`. **Sign-up redirects to `/profile/new`** (`forceRedirectUrl`).
- `lib/api.ts` now has a shared typed `apiFetch` seam + `ApiError` (carries the HTTP status so callers can branch on 404/409); `createProfile` / `postUserLocation` helpers route through it.

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

### PR B — Close the ML loop 🟡 OPEN as PR #8 (branch `claude/nifty-lamport-12eR7`)
**Goal:** the system not only *recommends* but also *measures whether
the recommendation was good*. This is the headline AI-engineering
story; bringing even a thin version forward now strengthens every
recruiter conversation.

Shipped in PR #8 (awaiting review/merge):
- ✅ `POST /recommendations/{impression_id}/outcomes` — idempotent,
  additive, Clerk-auth, ownership-checked. Records `viewed` /
  `profile_opened` / `friend_request_sent` / `hangout_rsvped`.
  (Dropped the planned `blocked` mapping — see DECISIONS_LOG: would
  have been a dishonest training label.)
- ✅ `GET /recommendations` mints + returns an `impression_id` per
  result and persists a `features_json` snapshot of raw ranker inputs
  (Alembic `0003`, nullable column).
- ✅ `apps/api/src/hangpost_api/recommendations/evaluation.py` — pure
  stdlib NDCG@10 / Recall@10 + popularity + random baselines, unit-tested
  without a DB.
- ✅ `apps/api/scripts/evaluate.py` — DB driver that groups
  impressions+outcomes into queries, scores live vs baselines, writes a
  markdown report to `docs/eval/`.
- ✅ `/demo` cards extracted into a client component that POSTs
  outcomes (`viewed` on mount, `profile_opened` on name click,
  `friend_request_sent` on Add friend). Dismiss is client-only.
- ✅ `docs/eval/README.md` + `SYNTHETIC-self-test.md` (live 0.93 vs
  popularity 0.58 vs random 0.57 NDCG@10 on synthetic inputs).

Outstanding for the PR: live-Codespaces verify of the outcome write
+ Alembic `0003` (CI doesn't have a DB-integration harness yet —
that's PR C). No code changes expected.

### PR C — Observable and presentable (queued, not started)
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

### PR D — ML-engineer polish (queued from 2026-05-30 assessment)
**Goal:** make the AI-engineering story legible at a glance. Each item
is a 1–2 hour change; ship them as one PR or one-at-a-time.
- `docs/MODEL_CARD.md` — what the ranker does, its inputs, its limits,
  known failure modes. Industry-standard responsible-AI artifact.
- `docs/DATA_CARD.md` — synthetic seed-corpus provenance, biases, why
  it isn't representative of real users.
- `docs/notebooks/eval.ipynb` — reproduces the NDCG@10 chart from
  `scripts/evaluate.py`. Notebooks are the ML interview lingua franca.
- `docs/PRODUCT_VISION.md` — port from sibling repo (CLAUDE.md §11
  references it; it doesn't exist here yet).
- Fairness stub in `evaluate.py`: group impressions by hometown / age
  bucket, log top-3 rate parity. Doesn't need to be sophisticated.

### Deployment (post-PR-C, blocks recruiter-shareable URL)
**Goal:** a clickable URL on the resume.
- Vercel for `apps/web`, Fly.io for `apps/api`, Neon for Postgres.
- Architecture already chose these (CLAUDE.md §3). Just needs the
  dashboard work and the secrets propagated.

Phase 2 (posts + feed) stays correctly blocked on Figma designs
(ADR-0005). All PRs above unblock independently of design and all
make the resume pitch stronger today.

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

### 2026-05-30 — Repo assessment + next-steps replan (no code)

- Re-read the repo on a fresh branch (`claude/gifted-dirac-kE49j`)
  with `main` merged through PR #7. Confirmed Phase 0 + Phase 1 +
  real-user demo loop are all on `main` as advertised.
- Confirmed **PR #8 is open**, contains the full PR B scope (outcome
  endpoint + `features_json` + offline NDCG/Recall eval + demo click
  handlers + synthetic self-test report), and is awaiting review/merge.
- Replanned next-steps queue with the AI-engineer resume audience as
  the explicit ranking key:
  1. Merge PR #8 (the headline ML-loop story).
  2. Verify the real-user demo against live Clerk in Codespaces (still
     needs the three Codespaces secrets per §"External inputs needed").
  3. Ship PR C (Sentry / structured logs / README rewrite / integration
     test / PRIVACY.md / sibling-repo tag swap).
  4. Ship PR D (MODEL_CARD + DATA_CARD + eval notebook + PRODUCT_VISION
     + fairness stub) — added this session.
  5. Deploy to Vercel + Fly.io + Neon so the resume can carry a URL.
  6. *Then* unblock Phase 2 (posts + feed) once Figma designs land.
- Catalogued improvements ranked by resume impact in the session
  reply (tiers 1–4). Highlights worth recording here so they don't get
  lost: model card, data card, eval notebook, fairness stub, OpenAPI →
  TS client into `packages/shared-types/` (directory exists but empty),
  Trivy + dependabot, embed-on-write → Arq, integration test against
  real Postgres in CI.
- No code changes this session. Memory only.

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
