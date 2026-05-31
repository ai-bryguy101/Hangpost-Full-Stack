# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we
> are*. `CLAUDE.md` tracks *what we decided*. ADRs track *why*. Updated
> at the **end** of every session in the same commit as the work.

Last updated: **2026-05-31**
Active branch: `claude/gifted-dirac-HtrVh` (assessment + memory refresh, no code)
Current phase: **Phase 1 ✅ complete + real-user onboarding shipped + PR B (ML-loop closure) open as PR #8 awaiting review**
Resume framing (CLAUDE.md §10): every next PR must strengthen the
"I shipped a recommender, evaluated it, and closed the loop on real
outcomes" pitch. If a change doesn't, postpone it.

---

## Phase status (mirrors `CLAUDE.md` §6)

| Phase | Status | Notes |
|---|---|---|
| 0. Foundation | ✅ done | Schema, ORM, seed, CI, ADRs 0001–0004. |
| 1. Auth + Profile + Matching | ✅ done | Engine pinned, 1,000 embeddings backfilled, `/recommendations` returns six-tier ranked output with `MatchBreakdown`, impressions logged, Clerk wired, `/demo` page renders results in a browser. End-to-end verified on docker-compose 2026-05-28. Real-user onboarding loop (`/profile/new` → location → JWT-only `/demo`) shipped 2026-05-29 (PR #7). |
| 1.5 ML-loop closure (PR B) | 🟡 in review | **PR #8 open**: outcome capture, `features_json` per impression, offline NDCG@10 / Recall@10 + popularity & random baselines, synthetic self-test report. Needs docker-compose smoke + one real eval report committed before merge. |
| 2. Location + Feed MVP | ⏳ blocked | On Figma/Stitch designs (ADR-0005). Pending operator call: hand-translate Stitch, commit raw, or ship shadcn-only first. |
| 3. Matching deepening | ⏳ | Outcome-capture half pulled into PR #8; UI deepening blocked on Phase 2. |
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

## ML / AI-engineering improvements catalogue (from 2026-05-31 assessment)

Improvements identified through a resume / AI-engineer-hiring lens.
Ranked by pitch-impact. Items already covered by PR B (#8) or PR C
are tagged so they aren't re-litigated.

| # | Item | Where it lands |
|---|---|---|
| 1 | Deploy a clickable live demo (Vercel + Fly.io + Neon) | **PR C** (top of list) |
| 2 | README rewrite: lead with the ML loop + one `/demo` screenshot + URL | **PR C** |
| 3 | Promote `model_version` from a config string to a `models` registry row (or S3 artifact) with `metrics_json` + `is_champion` flag | **New PR D**: prerequisite for Phase 7 A/B |
| 4 | `docs/models/rules-v1.md` model card (inputs, outputs, training data, known limitations, fairness statement) | **New PR D** |
| 5 | Slice-based evaluation in `scripts/evaluate.py` (cold-start, sparse-friend, age buckets, hometown-matched-vs-not) | **Extend PR B / PR D** |
| 6 | Fairness audit notebook at `docs/eval/fairness.ipynb` (disparate-impact check across hometown / college / age) | **Phase 7 prep** |
| 7 | Drift monitors: embedding-norm distribution, mutual-friend distribution, weekly recall@10 trend | **Phase 7** |
| 8 | Nightly GitHub Action that runs `scripts/evaluate.py` and commits the report | **PR C** (one extra workflow file) |
| 9 | Cut a tag on `hangpost-matching`, swap the SHA pin for `v0.x.y` | **PR C** |
| 10 | DB-backed integration test for `/recommendations` (boot mini seed corpus, assert ranking + breakdown shape) | **PR C** (already flagged in #8) |
| 11 | `docs/PRIVACY.md` — `user_locations` retention + delete-on-request | **PR C** |
| 12 | Sentry on browser + API | **PR C** |
| 13 | Structured ranker log line per call: model_version, latency, candidate count | **PR C** |
| 14 | Email-collision-on-Clerk-signup 500 → first-write-wins | **PR C** |
| 15 | Promote inline embed-on-write to Arq job once real traffic exists | **Phase 6** |
| 16 | Cold-start eval slice (users with no friends, no embedding) | **PR D** |
| 17 | Domain-adapted embedding model (fine-tune MiniLM on Hangpost bios) — stretch | **Phase 7 stretch** |

---

## Suggested next-steps order (post-2026-05-31)

1. **Smoke-test PR #8** on docker-compose, commit one real `docs/eval/` report, then merge.
2. **Set the three Clerk Codespaces secrets** and click through the live sign-up loop once. Without this, the app technically has zero verified users.
3. **PR C** (single bundled PR — none of its items justify a PR alone, together they make the repo *look* the way it already *behaves*): deploy → README → Sentry → structured logs → integration test → `PRIVACY.md` → tag swap → email-collision fix → nightly eval workflow.
4. **PR D — model registry + model card + slice eval.** Converts the repo from "candidate built a recommender" to "candidate built and *operated* a recommender."
5. **Decide Phase 2 design pipeline** so the posterboard feed can start. Recommendation: ship hand-coded shadcn/ui first, retro-fit Figma later.

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

### 2026-05-31 — Repo assessment + memory refresh (no code, branch `claude/gifted-dirac-HtrVh`)

- Re-read full repo, ADRs, STATUS, DECISIONS_LOG, PR #8, CI workflow,
  `recommendations/router.py`. Confirmed state: Phase 1 ✅, PR A merged
  (PR #7), PR #8 (PR B — ML-loop closure) **open and ready for review**,
  no open issues, working tree clean on `claude/gifted-dirac-HtrVh`.
- Catalogued 17 ML/AI-engineering improvements through a recruiter-lens
  (see new "improvements catalogue" section above). Grouped them onto
  PR C (already queued), a new **PR D** (model registry + model card +
  slice eval), and Phase 7.
- Surfaced gap: today the recommender is logged but *never deployed*.
  A live URL on the README is worth ten paragraphs of code for the
  AI-engineer pitch — promoted "deploy" to PR C item #1.
- Surfaced gap: `model_version` is a settings string. A real model
  registry (table or S3) is a prerequisite for the Phase-7 A/B
  harness; pulled forward into a new PR D ahead of full retraining.
- Surfaced gap: `evaluate.py` (PR #8) reports one global NDCG. Real
  ML systems report sliced metrics — added cold-start + age + hometown
  slices to PR D scope.
- Surfaced gap: no model card, no fairness audit, no drift monitors.
  These are the artefacts AI-engineering hiring managers grep for.
- Re-affirmed: Phase 2 (posts + feed) stays blocked on Figma
  (ADR-0005), but the operator needs to make the hand-translate
  vs. ship-shadcn-first call so the block doesn't become permanent.
- No code touched. Memory files updated: this `STATUS.md` and one new
  entry in `DECISIONS_LOG.md` (PR D scope + slice eval as a standard).

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
