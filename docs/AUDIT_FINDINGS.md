# Hangpost — Cross-Repo Self-Audit Findings

> **Read this at the start of the next session.** This is a compressed
> handoff from a critical self-audit performed 2026-05-31 across all
> three Hangpost repos. Every finding here is actionable; the goal of
> the next session is to start working down the list.

- **Audited by**: Claude Code self-review session (Opus 4.7)
- **Date**: 2026-05-31
- **Branches reviewed**:
  - `ai-bryguy101/Hangpost-Full-Stack@claude/vigilant-gates-ZjDf4`
  - `ai-bryguy101/hangpost-app@claude/pensive-wright-ZjDf4`
  - `ai-bryguy101/v0-hangpost@claude/elegant-babbage-ZjDf4`
- **Method**: Three parallel sub-agents read the code; one cross-repo
  pass on docs vs reality; web research on common LLM coding pitfalls
  and dating/social-app privacy issues to know what to look for.
- **Counts**: 112 raw findings → deduped to ~95 distinct issues across
  3 repos and 1 cross-repo bucket.
- **Severity legend**:
  - `CRIT` Launch blocker. Security, safety, or correctness so broken
    that shipping is irresponsible.
  - `HIGH` Required for a real public beta. Missing best-practice
    defaults; quiet correctness bugs.
  - `MED`  Important for scale/reliability/maintenance.
  - `LOW`  Polish, docs, observability nice-to-haves.
- **Vitality scale** (separate from severity — how much it advances the
  "I shipped a real product" pitch):
  - `★★★` Must do — fixes a thing that would embarrass us in any
    review, demo, or pen-test.
  - `★★`  Should do — meaningful quality bar.
  - `★`   Could do — polish.
- **Timeline buckets**:
  - `W0` This week (before another user touches the app)
  - `W1` Within 1-2 weeks (before any external demo)
  - `M1` Within a month (before public beta)
  - `BL` Backlog (post-launch, plannable)

---

## 0. TL;DR — top 12 things to fix first

| # | Issue | Where | Sev | Why first |
|---|---|---|---|---|
| 1 | **Two parallel Next.js frontends** (`apps/web` in full-stack repo AND the whole `v0-hangpost` repo) with different stacks, no shared types, diverging UX | cross-repo | CRIT | We are paying for the build twice and they will silently diverge. Pick ONE before any more UI work. |
| 2 | **No Trust & Safety primitives** anywhere — no block, no report, no content moderation hooks, no age verification beyond a number-in-a-form, no abuse rate-limit | both frontends + api | CRIT | A location-based "meet new strangers" app without these is a stalking/CSAM lawsuit waiting to happen. |
| 3 | **CSRF protection missing** on every state-changing endpoint, despite `CORS allow_credentials=True` (the worst combo) | `apps/api/main.py`, `lib/api.ts` | CRIT | Cross-site profile/location hijack on logged-in users. |
| 4 | **Joblib model loading is RCE** — signature check runs AFTER `joblib.load()` | `hangpost-app/src/hangpost_matching/learning.py:246-266` | CRIT | An attacker-controlled `.joblib` artifact = remote code execution in the API process. |
| 5 | **JWT `aud` verification is hardcoded off** with a TODO to fix "later" | `apps/api/.../auth/dependencies.py:60-76` | CRIT | A token issued to any other Clerk-using app is accepted as a Hangpost token. |
| 6 | **Exact GPS lat/lng stored & exact distance shown** to other users | `apps/api/.../profiles/locations.py:53`, `v0/app/feed/page.tsx:140`, `v0/lib/format.ts:12` | CRIT | Triangulation → real-world stalking. Industry standard is geohash quantize + 100m+ fuzz + bucketed distances. |
| 7 | **v0-hangpost is 100% seed data** — `USE_SEED_DATA = true`, signin is a `setTimeout`, every API call returns mocks | `v0-hangpost/lib/api.ts:37`, `app/onboarding/signin/page.tsx:14-20` | CRIT | If this is what gets demoed, the entire product is a lie. |
| 8 | **No rate limiting anywhere** on the FastAPI service | `apps/api/main.py` | CRIT | Profile enumeration, location spam, ranker DoS — all trivial. |
| 9 | **Email-collision on Clerk upsert returns HTTP 500** instead of 409, and STATUS.md says "fine for synthetic users" — it's not | `apps/api/.../auth/dependencies.py:94-120` | HIGH | Silent auth bug; account squatting risk in prod. |
| 10 | **Age constraint mismatch**: ORM model says 18-120, migration 0001 says 13-120, only migration 0002 fixes the DB — autogenerate will produce broken migrations | `apps/api/.../profiles/models.py:30` vs `alembic/versions/0001:61` | HIGH | The repo's own source of truth is internally inconsistent. |
| 11 | **`reports` table has no `ON DELETE CASCADE`** on FKs to users/posts | `alembic/versions/0001_initial_schema.py:181-182` | HIGH | GDPR delete leaves dangling rows that leak deleted user IDs. |
| 12 | **CLAUDE.md / Build Plan over-claims completion** — Phase 1 marked ✅ done but the "real-user UI" is described as "still pending" in STATUS.md, and the v0 repo isn't even referenced from the plan | docs across all repos | HIGH | We are confabulating progress to ourselves. |

Do these twelve in W0 and the project goes from "AI-generated demo
that won't survive a security review" to "credibly buildable v1."

---

## 1. Cross-repo structural issues (not caught by per-repo sub-audits)

These are the meta-issues that come from looking at the three repos
together.

### 1.1 `CRIT` — Two Next.js frontends, no source of truth
- **Symptom**: `Hangpost-Full-Stack/apps/web` (Next.js 15 + Clerk +
  TanStack Query + the API, all real) and the entire `v0-hangpost`
  repo (Next.js + Zustand + 100% seed data) both exist and both call
  themselves "the Hangpost web app."
- **Effect**: Duplicated work, divergent UX, no shared design system
  between the two, neither imports `packages/shared-types`.
- **Fix**: Decide **today**. Recommended: keep `apps/web` (it's the one
  inside the monorepo, already wired to Clerk + the real API, matches
  the Build Plan's repo layout). Port the *visual* polish from
  `v0-hangpost` into `apps/web` as components, then archive
  `v0-hangpost` with a README note pointing at the full-stack repo.
- **Vitality**: ★★★ — every other UI fix is wasted if we don't pick.
- **Timeline**: W0.

### 1.2 `HIGH` — Repo naming chaos vs the Build Plan
- The Build Plan §1 says the full-stack repo should be named
  `hangpost-app`, but `hangpost-app` is actually the **matching
  engine** repo (which CLAUDE.md says is "to be renamed
  `hangpost-matching-engine`"). The actual full-stack repo is named
  `Hangpost-Full-Stack` (capitalized, hyphenated differently).
- **Fix**: Rename one of:
  - `hangpost-app` → `hangpost-matching-engine` (matches CLAUDE.md
    promise), and either rename `Hangpost-Full-Stack` → `hangpost-app`
    (matches Build Plan) **or** update Build Plan to say
    `Hangpost-Full-Stack`.
- **Vitality**: ★★ — confusing for any reader; near-zero cost to fix.
- **Timeline**: W0.

### 1.3 `HIGH` — `packages/shared-types/` is an empty promise
- `Hangpost-Full-Stack/packages/shared-types/` contains only a README.
  CLAUDE.md §3 lists it as "OpenAPI-generated TS client — Phase 1."
  Neither `apps/web` nor `v0-hangpost` consumes it.
- **Fix**: Either (a) wire up `openapi-typescript` codegen in CI, run
  on every API change, and have `apps/web/src/lib/api.ts` import the
  types; or (b) delete the package and stop claiming it exists.
- **Vitality**: ★★★ — without a typed contract, "the frontend will
  just match the backend" never holds.
- **Timeline**: W1.

### 1.4 `HIGH` — CLAUDE.md vs `pr.yml` overclaim mismatch
- `CLAUDE.md §7` says PR CI does `ruff + mypy + eslint + tsc + pytest
  + vitest + docker build + Trivy scan + preview env on Fly.io +
  Playwright smoke`. `.github/workflows/pr.yml` honestly admits it
  does the first six only (Trivy/preview/Playwright are deferred to
  Phase 6).
- **Fix**: Reword CLAUDE.md §7 to match reality. Move the "future
  pipeline" prose into an appendix with `(planned)` markers.
- **Vitality**: ★★ — we lie to ourselves in the file we read every
  session.
- **Timeline**: W0 (5-minute fix).

### 1.5 `MED` — `docs/PRODUCT_VISION.md` referenced but missing
- CLAUDE.md §11 says "Product vision (long-form): `docs/PRODUCT_VISION.md`
  (port from sibling repo)" but the file doesn't exist in the full-stack
  repo. `hangpost-app` has a `PRODUCT_VISION.md` at the root; it was
  never ported.
- **Fix**: `cp` from sibling repo into `Hangpost-Full-Stack/docs/`,
  diff and reconcile.
- **Vitality**: ★ — easy.
- **Timeline**: W0.

### 1.6 `MED` — No PRIVACY.md, no TOS, no data-retention policy
- The product collects exact GPS, contacts, age, hometown, college,
  interests, embeddings. None of the three repos has a PRIVACY.md.
  CLAUDE.md mentions GDPR `consent_hash` in the schema but no policy
  document explains what we do with that data.
- **Fix**: Even a draft `PRIVACY.md` + `TERMS.md` in the full-stack
  repo (this is the "official" repo) covering: what's collected,
  retention, deletion, third-party processors (Clerk, Vercel, Neon,
  Sentry, Cloudflare R2), age requirement (18+), block/report
  procedure.
- **Vitality**: ★★★ — required by GDPR/CCPA the moment a real user
  signs up; FTC enforcement under COPPA risks 6-figure penalties per
  violation if any user is under 13.
- **Timeline**: W1 (legal review M1).

### 1.7 `HIGH` — No Trust & Safety surface area at all
- No block, no report, no abuse-rate-limit, no content moderation
  hooks, no shadow ban, no IP/geo abuse heuristics, no human-review
  queue, no T&S oncall doc, no DSA/SCSA notice scaffold. The matching
  engine has a `LearnedRanker` but no "demote bad actors" feature in
  the ranker either.
- **Fix**: T&S epic. At minimum for v1:
  1. `POST /reports` endpoint + `reports` table (table exists; no
     endpoint).
  2. `POST /blocks` endpoint + `user_blocks` table (table exists;
     no endpoint or filter).
  3. Pre-filter blocked users out of `/recommendations` candidate set.
  4. Rate limit auth, profile create, location update, reports.
  5. Add Block / Report buttons on every profile card.
  6. Operator review tool — even just an SQL playbook in
     `docs/RUNBOOK.md` for now.
- **Vitality**: ★★★ — see TL;DR #2.
- **Timeline**: W1 (full M1).

### 1.8 `HIGH` — Cross-repo data model inconsistency risk
- The matching engine's `UserProfile` (Pydantic-ish dataclass) and the
  API's `Profile` SQLAlchemy model both define profile fields. There
  is no compile-time check they agree (no shared schema, no contract
  test). Adding a field on one side is silent on the other.
- **Fix**: Either (a) make the matching-engine `UserProfile` *the*
  source of truth and have the API construct it via Pydantic
  validators that the test suite exercises against every DB profile;
  or (b) add a `tests/test_profile_schema_contract.py` that fails CI
  if the field sets don't match.
- **Vitality**: ★★ — quiet correctness drift.
- **Timeline**: M1.

---

## 2. Hangpost-Full-Stack (backend + apps/web)

Findings from the per-repo sub-agent, lightly re-organized and
augmented with fixes/vitality/timeline. File paths are relative to
`Hangpost-Full-Stack/`.

### 2.A Security (CRITICAL)

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| F1 | `apps/api/src/hangpost_api/main.py` (entire app) | No rate limit on any endpoint | Add `slowapi` or `fastapi-limiter` middleware; per-IP and per-Clerk-sub buckets; tight on auth & location & profile-create | CRIT | ★★★ | W0 |
| F2 | `apps/api/src/hangpost_api/main.py` (CORS) + `apps/web/src/lib/api.ts:44-48` | No CSRF protection with `allow_credentials=True` | Switch to `SameSite=Lax` cookies + double-submit token, OR move to `Authorization: Bearer` and drop credentialed CORS | CRIT | ★★★ | W0 |
| F3 | `apps/api/src/hangpost_api/auth/dependencies.py:60-76` | `verify_aud=False` hardcoded | Re-enable, set expected audience to the Clerk frontend API URL; document in ADR | CRIT | ★★★ | W0 |
| F4 | `alembic/versions/0001_initial_schema.py:181-182` | `reports.reporter_id / target_user_id / target_post_id` missing `ON DELETE CASCADE` (or `SET NULL`) | New migration adding the FK cascades; decide CASCADE vs SET NULL per column based on what we want post-deletion | CRIT | ★★★ | W0 |
| F5 | `apps/api/src/hangpost_api/profiles/models.py:30` vs `alembic/versions/0001:61` | ORM age constraint says 18-120, migration 0001 says 13-120 | Pick one (must be 18+ for safety), align ORM, drop the constraint in 0001, re-create in a single migration; document why no minors | HIGH | ★★★ | W0 |
| F6 | `apps/api/src/hangpost_api/auth/dependencies.py:94-120` + `auth/models.py:26` | Email collision on second Clerk `sub` triggers `IntegrityError` → 500 | Catch `IntegrityError` on email-unique; return 409 with a specific `error_code="email_taken"`; never 500 on user input | HIGH | ★★★ | W0 |
| F7 | `apps/api/src/hangpost_api/main.py` (middleware stack) | No security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy) | Add `secure-headers` style middleware on the API and a `next.config` headers block on the web | HIGH | ★★★ | W1 |
| F8 | `apps/api/src/hangpost_api/auth/dependencies.py` | No structured logging of failed auth attempts | Emit a single-line JSON log `{"event":"auth_fail","reason":..,"ip":..}`; later feed into a counter | LOW | ★★ | W1 |
| F9 | `apps/api/src/hangpost_api/profiles/locations.py:53` | Raw lat/lng stored at full precision | Quantize to 4 decimal places (~11m) on write; store geohash5 alongside; show only bucketed distance bands ("<0.5mi", "0.5-2mi", "2-5mi") in the UI | CRIT | ★★★ | W1 |
| F10 | `apps/api/src/hangpost_api/profiles/locations.py` | No throttle on `POST /user-locations` | Rate limit 1/min per user; also reject updates where new position is <50m from last AND <60s elapsed (no-op) | HIGH | ★★ | W1 |

### 2.B Architecture / correctness

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| F11 | `apps/api/pyproject.toml:32` | Matching engine pinned by commit SHA on an untagged untyped repo | Publish the matching engine to PyPI (or at least tag it); switch to a version pin; lock file via `uv` or `pip-compile` | MED | ★★★ | W1 |
| F12 | `apps/api/pyproject.toml:10-32` | All deps `>=` with no lock file → non-reproducible | Generate `uv.lock` / `requirements.lock`; commit it; use it in Dockerfile | MED | ★★ | W1 |
| F13 | `infra/compose/` (no backup config) | No DB backup strategy or runbook | Document Neon point-in-time recovery in `RUNBOOK.md`; add nightly `pg_dump` cron for the local dev stack; RTO/RPO note | MED | ★★ | M1 |
| F14 | `alembic/versions/` | Downgrade paths exist but never tested | Add CI job `pytest tests/test_migrations_roundtrip.py` that applies up→down→up on an ephemeral DB | MED | ★★ | M1 |
| F15 | `apps/api/src/hangpost_api/profiles/router.py:68-102` | `create_profile` does inline embed (50ms-2s) blocking the request | Move embed to Arq worker; profile saved without embedding; recommendation excludes profiles with NULL embedding until backfilled | MED | ★★ | M1 |
| F16 | `apps/api/src/hangpost_api/main.py` (CORS) | No `max_age` on preflight | `CORSMiddleware(max_age=86400)` | LOW | ★ | W1 |
| F17 | `apps/api/src/hangpost_api/profiles/router.py:98-101` | All errors are `HTTPException(detail=str)` — no error codes | Return `{error: {code, message, fields?}}` everywhere; FE switches on `code` not message string | MED | ★★ | M1 |
| F18 | `apps/api/src/hangpost_api/recommendations/router.py:256-266` | Every impression logs the full `MatchBreakdown` JSONB → ranker reverse-engineerable from a data dump | Log score + top 3 feature contributions only; full breakdown only behind a debug flag | MED | ★★ | M1 |
| F19 | `apps/api/src/hangpost_api/recommendations/router.py:48-51` | Magic numbers: `DEFAULT_RADIUS_M = 5_000`, `MAX_RADIUS_M = 50_000` | Move to `settings.py` constants with docstring rationale; consider per-city defaults | LOW | ★ | M1 |
| F20 | `apps/api/seed.py:49-54` + `seed.py:66-70` | Hardcoded DC center, hardcoded CSV paths | Inject via env var; raise a friendlier error than `FileNotFoundError` listing paths searched | LOW | ★ | M1 |
| F21 | `apps/api/src/hangpost_api/main.py:89-94` | `/health/ready` is just `SELECT 1` — no Redis, no engine warmup check | Extend readiness probe to also ping Redis and assert matching engine import; document SLO | LOW | ★★ | M1 |
| F22 | `apps/api/tests/` | Only smoke 401 tests, no integration coverage | Add integration tests with a postgres test container: profile create+location+recommend round-trip | MED | ★★ | M1 |
| F23 | `apps/web/src/middleware.ts` | Auth not enforced in middleware; each page does its own check | Adopt route-segment `(authed)` group with shared middleware guard; document the pattern in `ARCHITECTURE.md` | LOW | ★ | M1 |
| F24 | `alembic/versions/0001:197` | `notifications.payload` is freeform JSONB with no schema | Define a `NotificationPayload` discriminated union in Pydantic; validate before write | LOW | ★★ | M1 (before Phase 4 ships) |
| F25 | `infra/docker/api.Dockerfile` | Docker image likely runs as root, no HEALTHCHECK | Add `USER appuser`, add `HEALTHCHECK CMD curl -f http://localhost:8000/health/ready` | MED | ★★ | W1 |

### 2.C Docs vs reality

| # | Where | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| F26 | `README.md:39-44` | Claims "Phase 0 done" while CLAUDE.md says "Phase 1 done" | One source of truth — STATUS.md. README and CLAUDE.md cite it. | LOW | ★★ | W0 |
| F27 | `Hangpost Full-Stack Build Plan.md` | Plan references repo as `hangpost-app/`; actual repo is `Hangpost-Full-Stack/` and `hangpost-app` is a different thing | Add a §0.5 "How this plan maps to today's repos" with the rename note | LOW | ★ | W0 |
| F28 | `docs/STATUS.md` (the email-collision admission) | Calls a 500 bug "fine for synthetic users" — that's not how we judge bugs | Reword: list as a known bug with ticket, don't excuse it | LOW | ★★ | W0 |
| F29 | `.gitignore` | Confirm `.next/`, `__pycache__/`, `.venv/`, `*.joblib` are listed | If missing, add | LOW | ★ | W0 |

---

## 3. hangpost-app — matching engine

File paths relative to `hangpost-app/`.

### 3.A Security

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| M1 | `src/hangpost_matching/learning.py:246-266` | **Joblib RCE**: signature check runs *after* `joblib.load()` | Verify HMAC of the bytes **before** unpickling; reject unsigned files entirely; consider switching to a non-pickle serialization (LightGBM native `txt` format) | CRIT | ★★★ | W0 |
| M2 | `src/hangpost_matching/server.py:161-169` | If `HANGPOST_MODE=learned` and model file missing, server fails to boot with no fallback | Fall back to rules ranker, log `WARN` and surface in `/health`; never let a missing model take the service down | HIGH | ★★★ | W0 |
| M3 | `src/hangpost_matching/server.py:252-255` | Embeddings re-encoded per `/rank` request (no cache, O(N) per call) | Precompute on profile write upstream; in-process LRU on embeddings keyed by profile hash; document the contract | HIGH | ★★ | W1 |
| M4 | `src/hangpost_matching/server.py:257-273` | `LearnedRanker(...)` instantiated per request | Bind at startup; mutate per-request only inputs | HIGH | ★★ | W1 |

### 3.B Correctness / algorithm

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| M5 | `src/hangpost_matching/scoring.py:162-164` | `_bounded_ratio(mutual_friend_count, 20)` magic `20` | Move to product-configured constant; document in MODEL_CARD; consider log-scaling to avoid saturation cliff | HIGH | ★★ | W1 |
| M6 | `src/hangpost_matching/scoring.py:95-112` | Age step-down `1 - 0.1*gap` is arbitrary, hard zero at gap=10 | Replace with smooth Gaussian or logistic, fit on judge labels; report ablation in MODEL_CARD | HIGH | ★★ | M1 |
| M7 | `src/hangpost_matching/embeddings.py:38-54` | Cosine sim returns 0.0 on zero-norm vectors (silently conflates orthogonal with degenerate) | Return `None` or skip the signal; ranker treats missing similarity as a downweight, not a 0 score | MED | ★★ | M1 |
| M8 | `src/hangpost_matching/learning.py:138-174` | No assertion that `features` and `labels` align after the loop | `assert len(features) == len(labels)`, or build them as one list of tuples | HIGH | ★★ | W1 |
| M9 | `src/hangpost_matching/evaluation.py:335-361` | `_stable_personality_vector` SHA256 + 4-byte chunking is lossy and undocumented | Add a docstring explaining it's a *deterministic-but-not-private* surrogate; rename to make the simulation intent obvious | LOW | ★ | M1 |
| M10 | `src/hangpost_matching/data.py:37-44` | Synthetic mutual-friend IDs always overlap deterministically → evaluation cheats | Generate realistic friend graphs with controlled overlap distributions; rerun evaluations | MED | ★★ | M1 |
| M11 | `src/hangpost_matching/scoring.py:268-307` (cold start) | `rank_candidates_with_cold_start` has no evaluation case in the harness | Add a cold-start eval split; report metrics in MODEL_CARD | HIGH | ★★ | M1 |

### 3.C Evaluation / fairness gaps

| # | Where | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| M12 | `docs/MODEL_CARD.md:145` | Self-admitted: no subgroup fairness audit | Run demographic parity + equality of opportunity on synthetic + judge labels split by (age band, hometown rarity, mutual-friend density); publish gap thresholds | HIGH | ★★★ | M1 |
| M13 | repo-wide | LLM-judge labels never compared against any real-world ground truth | Even N=50 hand-labelled pairs gives an upper bound on judge bias; do it before any "distilled from real labels" pitch | HIGH | ★★ | M1 |
| M14 | `src/hangpost_matching/evaluation.py:147-169` | `intra_list_diversity` silently skips candidates with no embedding | Document; treat as a coverage metric, not a diversity metric, unless we backfill | MED | ★ | M1 |
| M15 | `README.md:36-54` | Headline NDCG numbers reported without confidence intervals on N=9 queries | Bootstrap CIs; report ±. Honest framing: "directional, not significant" | LOW | ★★ | W1 |

### 3.D Production readiness

| # | Where | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| M16 | `src/hangpost_matching/server.py:136-137` | `requests_seen` / `candidates_seen` counters not exposed | `/metrics` Prometheus endpoint; or push to OTel; structured log on shutdown at minimum | LOW | ★★ | W1 |
| M17 | `pyproject.toml:52-67` | `>=` only on heavy optional deps (`sentence-transformers`, `lightgbm`, `anthropic`) | Upper-bound the majors (`<3`, `<5`, `<1` etc); test on the lower bound in CI | LOW | ★ | M1 |
| M18 | `scripts/label.py`, `gold_label.py` | No checksum / version stamp on `judge_labels.jsonl` | Add a header JSON line with `{judge_model, prompt_sha, schema_version, generated_at}` | MED | ★★ | M1 |
| M19 | `scripts/train.py:227-240` | `--labels` silently overrides `--relevance` if both passed | Make them mutually exclusive at the argparse level | LOW | ★ | W1 |
| M20 | `tests/test_*` | Tests cover happy paths only; no edge cases (all-None fields, homonyms, etc.) | Property-based tests with `hypothesis` for the scoring function | MED | ★★ | M1 |
| M21 | `.github/workflows/ci.yml:44-79` | `ml-smoke` job trains the ranker but never asserts on metrics → passes even if model is broken | Assert NDCG@5 on a fixed seed is within ε of a baseline | MED | ★★ | W1 |

### 3.E Docs vs reality

| # | Where | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| M22 | `matching_algorithms_explainer.md` (~18KB) | Reads as a generic intro-to-matching tutorial; doesn't describe THIS repo's actual choices | Rewrite as "Hangpost matching, explained" with concrete code refs; move the tutorial to an appendix | MED | ★★ | M1 |
| M23 | `docs/MODEL_CARD.md:42-44` | "Out of scope: decisions with material consequences" is buried | Bring to top of card; spell out specifically what "consequential" means (employment, credit, housing — none of those, ever) | LOW | ★ | M1 |
| M24 | `docs/DATA_CARD.md:38-66` | Synthetic profile generation process undocumented | Document the generator (`src/hangpost_matching/data.py`); list biases (geographic concentration in DC seeds, interest list curation) | MED | ★★ | M1 |
| M25 | `CLAUDE.md` (matching repo) | Says repo is "to be renamed `hangpost-matching-engine`" — never executed | Rename now; the longer we wait the worse the cross-repo confusion (see §1.2) | LOW | ★★ | W0 |

---

## 4. v0-hangpost — separate Next.js prototype

File paths relative to `v0-hangpost/`. **Many of these stop mattering
if we adopt §1.1 and retire v0-hangpost.** Marked `[archive-OK]` for
findings that are moot if we archive the repo.

### 4.A Critical "it's all fake" issues

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V1 | `lib/api.ts:37` | `const USE_SEED_DATA = true` — every API call returns mocks | Flip to `false` (after §1.1 decision); wire to real `apps/api` endpoints | CRIT | ★★★ | W0 |
| V2 | `app/onboarding/signin/page.tsx:14-20` | Sign-in is `setTimeout(1500)` then redirect | Replace with Clerk `<SignIn>` widget — same as `apps/web` | CRIT | ★★★ | W0 |
| V3 | `lib/match.ts` | Match algorithm is hardcoded reasons, no scoring | Call real `/recommendations`; render returned `MatchBreakdown` | CRIT | ★★★ | W0 |
| V4 | `next.config.mjs:3-5` | `ignoreBuildErrors: true` and `ignoreDuringBuilds: true` for ESLint | Remove both; fix the resulting errors | HIGH | ★★ | W0 [archive-OK] |
| V5 | `app/create-profile/page.tsx` (no auth wall) | Anyone reaches protected pages without a session | Add a middleware that redirects unauthenticated users to `/onboarding/signin` | CRIT | ★★★ | W0 [archive-OK] |

### 4.B Privacy & safety

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V6 | `app/feed/page.tsx:140`, `app/matches/page.tsx:146`, `lib/format.ts:12` | Exact distance (`0.3 mi`) displayed → triangulation | Replace with banded distance: `<0.5 mi`, `0.5-2 mi`, `2-5 mi`, `5+ mi` | CRIT | ★★★ | W0 [or port to apps/web] |
| V7 | every profile/match/feed page | No Block / Report buttons | Add `<BlockButton>` and `<ReportButton>` to every user-rendered card; wire to backend (after F-something endpoints exist) | CRIT | ★★★ | W1 |
| V8 | `stores/use-app-store.ts:13-15,22-26` | Location prefs in localStorage with no consent screen | Consent banner on first load; settings toggle to wipe; localStorage values encrypted is overkill, but minimize what's there | HIGH | ★★ | W1 |
| V9 | `stores/use-app-store.ts:29-34` | App preferences (city, radius) in plaintext localStorage | Move to httpOnly cookies set by API; or scope to session storage only | MED | ★ | M1 |
| V10 | `lib/seed.ts:32,46,57,79,89,100` | User IDs embedded in third-party avatar URLs (`pravatar.cc?u=user_id`) | Don't ship user IDs to third parties; proxy avatars through our domain | MED | ★★ | W1 [archive-OK] |
| V11 | `app/onboarding/contacts/page.tsx:57-81` | Contacts onboarding copy promises privacy but does no actual import (no permission prompt) — implies consent already given | Either implement opt-in contact sync with explicit prompts, or remove the screen | HIGH | ★★ | W1 |
| V12 | `app/create-profile/page.tsx` (age field) | Age collected as a number with no verification → 12-year-old enters 18 | Self-declared age + delayed verification (Stripe Identity / Persona for 18+ gate) before unlocking features; under-18 must be blocked from app, not just matching | CRIT | ★★★ | M1 |
| V13 | no MFA UI | No 2FA/MFA path | Clerk MFA setting + opt-in CTA in settings | MED | ★★ | M1 |

### 4.C Architecture / Next.js misuse

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V14 | 10/12 pages | `'use client'` on every page → no SSR, fat bundles | Convert data fetches to Server Components; keep client islands for interactivity | HIGH | ★★ | W1 [if not archiving] |
| V15 | `app/` | No `loading.tsx`, no `error.tsx`, no `not-found.tsx` | Add baseline files at the root segment | MED | ★★ | W1 |
| V16 | API mutations | Done client-side via `fetch` — no Server Actions | Use Server Actions or call the FastAPI from a Route Handler so we can attach the user's session server-side | MED | ★★ | M1 |
| V17 | `components/create-hangout-sheet.tsx:59-199` | Sheet modal with no focus trap | Use Radix Dialog primitives correctly; verify focus return on close | MED | ★★ | M1 |
| V18 | `next.config.mjs:7` | `images.unoptimized = true` + no `remotePatterns` | Add specific remote patterns for our R2 bucket; turn optimization on | MED | ★★ | W1 |
| V19 | `package.json:15-41` | Every shadcn primitive installed even if unused | Tree-shake aided by build; cosmetic; remove a few obviously unused ones | LOW | ★ | BL |
| V20 | `app/layout.tsx:19` only metadata | Only root metadata; no per-page `generateMetadata` or OpenGraph | Add per-route metadata as pages are built out | LOW | ★ | M1 |
| V21 | `app/manifest.ts` exists but no service worker | Not actually a PWA despite mobile-first claims | Add `next-pwa` (or roll a minimal SW) for offline shell + push reception (later) | MED | ★★ | M1 |
| V22 | `vercel.json` | One-liner; no edge config, no headers | Add security headers, env validation, region pinning | LOW | ★ | M1 |

### 4.D Security headers / config

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V23 | `next.config.mjs` | No CSP, no HSTS, no Permissions-Policy | Add `headers()` block in next.config (or middleware) | HIGH | ★★ | W1 |
| V24 | `.env.example:3` | `NEXT_PUBLIC_API_URL=http://localhost:8000` — easy to leave HTTP in prod | Add `validate()` in `lib/env.ts` with zod; refuse to start if production + HTTP | HIGH | ★★ | W0 [archive-OK] |
| V25 | `lib/api.ts:124-206` | No CSRF token on mutations | Cross-ref F2: server-side fix; FE should attach the token where applicable | HIGH | ★★ | W0 |
| V26 | `lib/api.ts:39-46` | Env vars checked at runtime, not build | `zod-env` or `t3-env` schema | LOW | ★ | M1 |
| V27 | no error tracking | No Sentry / no analytics events | Add Sentry SDK; tag releases | MED | ★★ | M1 |
| V28 | no session timeout | Mock signin never expires | Clerk handles when real; until then this is moot | MED | ★ | tied to V2 |

### 4.E Accessibility

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V29 | `components/avatar.tsx:28`, feed/matches pages | Generic alt text on user images | Use `${displayName} avatar`; localize | MED | ★★ | M1 |
| V30 | `app/bottom-tab-bar.tsx:37` and other icon buttons | Some icon-only buttons missing `aria-label` | Audit pass; add labels | MED | ★★ | W1 |
| V31 | `components/create-hangout-sheet.tsx` | No focus trap | Same as V17 | MED | ★★ | M1 |
| V32 | All sections | No tabindex / aria-expanded / aria-controls on disclosures | Audit pass | LOW | ★ | M1 |

### 4.F Form / input validation

| # | File:line | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V33 | `app/create-profile/page.tsx` (hometown/college fields) | Plain `Input` — no sanitization | Server-side strip HTML; client-side `maxLength` and pattern validation | MED | ★★ | W1 |
| V34 | `components/create-hangout-sheet.tsx:31,123` | Hardcoded `location = 'Current location'`, "would open picker" comment | Real geocoded picker (Mapbox / Google Places) or remove the form | MED | ★★ | M1 |
| V35 | `app/notifications/page.tsx:29-31` | `useEffect` missing `setNotifications` dep | Use `useMemo` instead, or refactor to skip the local state | LOW | ★ | W1 |
| V36 | misc handlers | Untyped event handlers | Add explicit types | LOW | ★ | BL |

### 4.G Vibes vs reality

| # | Where | Issue | Fix | Sev | V | When |
|---|---|---|---|---|---|---|
| V37 | `README.md` | "Linked to v0 project, every merge auto-deploys" + no mention of stub status | Add a banner: "Prototype only — see Hangpost-Full-Stack for the real frontend" | HIGH | ★★ | W0 |
| V38 | every "Coming soon"-shaped page | Real-looking UI fed by `lib/seed.ts` | After §1.1: archive | CRIT | ★★★ | W0 |

---

## 5. Suggested fix sequence

### W0 — this week (security + structural)
1. **Decide §1.1**: keep `apps/web`, archive `v0-hangpost`. (1h)
2. **F1 rate limiting** on `/auth`, `/profiles`, `/user-locations`,
   `/recommendations`. (½ day)
3. **F2 CSRF**: switch to bearer tokens + drop credentialed CORS, or
   add double-submit token. (½ day)
4. **F3 JWT `aud`**: re-enable, configure for our Clerk instance. (1h)
5. **F4 / F5 / F6**: write Alembic migration `0003_audit_fixes`
   (cascade reports, normalize age constraint, ensure ORM matches).
   (½ day)
6. **M1 joblib RCE**: verify signature before unpickle; switch to
   LightGBM native serialization where possible. (½ day)
7. **F9 / V6 location privacy**: quantize on write; banded display.
   (½ day)
8. Patch docs: §1.4 CI claim, §1.5 PRODUCT_VISION.md port, §1.2 repo
   rename plan, F26/F27/F28 doc reconciles. (1-2h)

**End of W0**: pen-tester wouldn't immediately laugh.

### W1 — before any external demo
- F7 / V23 security headers everywhere.
- F8 auth-fail logging.
- F10 location update throttle.
- F11 publish matching engine; lockfile (F12).
- M2 graceful learned-mode fallback; M3 cache embeddings; M4 bind
  ranker at startup.
- T&S §1.7 phase 1: ship `POST /reports`, `POST /blocks`, filter
  blocked from `/recommendations`, UI buttons.
- §1.6 draft PRIVACY.md + TERMS.md.
- §1.3 stand up `packages/shared-types` codegen.
- F25 Dockerfile non-root + HEALTHCHECK.
- V15 baseline `error.tsx` / `loading.tsx` / `not-found.tsx`.
- V18 image config tighten.
- M15 / M21 honest evaluation reporting.

### M1 — before public beta
- F13-F18, F22, F24 — backups, migration round-trip tests,
  observability, integration tests, error schema, breakdown
  data-minimization.
- M6 / M7 / M10 / M11 / M12 / M13 / M14 — fairness audit and
  algorithm hardening.
- M16-M20 / M22-M24 — observability and docs.
- V12 age verification (Stripe Identity).
- V13 MFA.
- V14 / V16 Server Components & Server Actions on web (if applicable).
- V21 PWA.
- V27 Sentry.

### BL — backlog
- V19 / V36 cosmetics.

---

## 6. Generalizable patterns we (Claude) keep falling into

Things to watch for in *every* future session. Treat these as
self-imposed lints.

1. **Confabulated completion.** STATUS.md says Phase 1 ✅ but the
   "real-user UI" follow-on is "still pending" — that's not done.
   Either it's done or it isn't. No "done with caveats."
2. **Documenting the future as if it's present.** CLAUDE.md §7 lists
   a CI pipeline that doesn't exist; PRODUCT_VISION.md is referenced
   but absent. Rule: a doc may only describe code that is on `main`.
3. **Mock data forever.** `USE_SEED_DATA = true` is fine for
   prototyping; it must die before "done." Rule: if a flag's `true`
   value disables a feature, gate the flag at build time.
4. **Insecure-by-default that's intentional.** `verify_aud=False`
   with a "tighten later" comment is a vulnerability today, not a
   TODO. Rule: any security default that's off must be tracked in a
   `SECURITY_TODO.md` and the CI must fail until cleared.
5. **CORS `allow_credentials=True` without CSRF.** The most common LLM
   trap in FastAPI scaffolds. Rule: if `allow_credentials=True`, the
   review checklist must include CSRF strategy.
6. **Pickle / joblib loading from disk treated as safe.** It is RCE
   if any attacker can swap the file. Rule: never load pickle
   without HMAC; prefer non-pickle formats.
7. **Magic numbers in scoring code.** `0.1 * gap`, `max=20` — these
   *are* product decisions and need MODEL_CARD entries.
8. **Synthetic data evaluations presented as evidence.** N=9 queries,
   no CIs, synthetic mutual-friend cheating — every number we publish
   must come with how it was made and how it could be wrong.
9. **Generic LLM tutorials masquerading as docs.** The 18KB
   matching_algorithms_explainer.md teaches matching in general; it
   doesn't explain *our* matching. Rule: docs reference our files +
   line numbers.
10. **Generating new code instead of integrating.** v0-hangpost is a
    second frontend we generated rather than evolving `apps/web`.
    Rule: if a working version exists, evolve it.
11. **Trust & Safety treated as a "later phase."** For a
    location-based stranger-meeting app, T&S is the product, not a
    backlog ticket. Rule: any feature involving user-to-user contact
    ships with block + report + rate-limit on day one.
12. **Forgotten the user is a real person who can be stalked.** Every
    location display, every distance string, every "X is N feet away"
    needs the question: can someone harm a user with this signal?

---

## 7. How to use this file in the next session

1. Open this file first. Skim §0 TL;DR.
2. Pick a W0 item; create a feature branch `claude/<session>-fix-<topic>`.
3. **Update this file** after fixing — strike through and link the PR
   (or move to a "DONE" section at the bottom). Don't let the audit
   bit-rot.
4. When all W0 items are done, do another audit pass to confirm; then
   move on to W1.
5. If you find new issues, add them with the same format; date them.

— end of audit —
