# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we are*.
> `CLAUDE.md` tracks *what we decided*. ADRs track *why*. This file is the
> running ledger of progress and is updated at the **end** of every session,
> in the same commit as the work.

Last updated: **2026-05-28**
Active branch: `claude/hopeful-volta-ZOBFt`
Current phase: **Phase 1 complete — verified end-to-end against the docker-compose stack on 2026-05-28**

---

## Phase status (mirrors `CLAUDE.md` §6)

| Phase | Status | Notes |
|---|---|---|
| 0. Foundation | ✅ done | Schema, ORM, seed (1,001 DC profiles), CI, ADRs 0001–0004 |
| 1. Auth + Profile + Embeddings + `/recommendations` | ✅ done | 1.1–1.6 landed and verified end-to-end on docker-compose. 1,000 profiles seeded + embedded; `GET /recommendations` returns the engine's six-tier sort with semantic-similarity 0.84–0.88 on top candidates; `recommendation_impressions` logs every surfaced row. Clerk-auth path is wired but only smoke-tested (the seed corpus has no Clerk identities by design). |
| 2. Location + Feed MVP | ⏳ blocked on Figma/Stitch designs (ADR-0005) |
| 3. Matching integration | partly absorbed into revised Phase 1 |
| 4. Hangouts + Real-time | not started |
| 5. Friend graph + Social | not started |
| 6. Observability + hardening | not started |
| 7. Close the ML loop | not started |

---

## What is done

- Monorepo scaffolded (`apps/api`, `apps/web`, `packages/`, `infra/`, `docs/`).
- Postgres + PostGIS + pgvector schema in one Alembic migration (`0001_initial_schema.py`); HNSW + GIST indexes already in place.
- ORM models exist for every domain (`auth`, `profiles`, `posts`, `hangouts`, `social`, `safety`, `notifications`, `recommendations`, `matching`).
- 1,001 synthetic DC profiles seeded by `python -m hangpost_api.seed` (idempotent, `auth_provider='seed'`).
- Local stack runs end-to-end via `docker compose -f infra/compose/docker-compose.yml up --build`.
- CI green: ruff + mypy + pytest (API), eslint + tsc + vitest + build (web), Docker builds for both.
- ADRs 0001–0004 locked in.
- Memory infra (this file + `DECISIONS_LOG.md`) added.

## What is intentionally NOT done yet

- No frontend wiring yet — `apps/web` is one health-check landing page. Real UI waits on Phase 2 + Figma designs.
- `/recommendations` still accepts `source_user_id` as a query param when no JWT is sent. Transitional fallback so the seed corpus stays demoable; drop it once the web app is on Clerk.
- No Arq worker for embed-on-write yet — embedding runs inline on `POST /profiles` and `PATCH /profiles/me` (single-encode latency ~50 ms once the model is warm, ~2 s cold). Move to Arq when API box gets traffic.
- Email-collision handling on the Clerk user upsert is first-write-wins; a second sub registering the same email will 500. Fine while users are synthetic; revisit before public launch.

## Verify pass (2026-05-28)

Booted the docker-compose stack in Codespaces and walked the demo path
end-to-end. Top-3 results against a random seed user returned hometown
+ college matches with `semantic_similarity` in the 0.84–0.88 range —
real engine signal flowing through pgvector → engine → JSONB log. Fixes
caught during the verify pass:

- `infra/docker/api.Dockerfile`: install CPU-only torch first
  (`--index-url https://download.pytorch.org/whl/cpu`); the default
  wheel pulled `nvidia-cudnn-cu13` and filled the Codespace disk.
- `apps/api/src/hangpost_api/seed.py` + Dockerfile: ship `apps/api/seeds`
  inside the image, and resolve `DEFAULT_CSV` across three known
  locations so non-editable installs work.
- `apps/api/src/hangpost_api/recommendations/router.py`: coerce
  `Profile.embedding` from pgvector's numpy array to plain Python floats
  before passing to the engine — otherwise `numpy.float32` leaked into
  `MatchBreakdown.semantic_similarity` and crashed `json.dumps` on the
  JSONB column.

## What landed this session — Phase 1.4–1.6 (2026-05-28)

- `auth/dependencies.py` — PyJWT + PyJWKClient verify Clerk JWTs against `CLERK_JWKS_URL`; upsert the `users` row on first sight. Two dependencies: `get_current_user` (required) and `get_current_user_optional` (used by `/recommendations`).
- `auth/router.py` + `auth/schemas.py` — `GET /me` returns the authenticated `User` as a `MeRead`.
- `profiles/schemas.py` — `ProfileCreate` (handle regex, age 13–120, dedupe-on-write) / `ProfileUpdate` (partial, `model_dump(exclude_unset=True)`) / `ProfileRead`.
- `profiles/embedder.py` — process-cached `SentenceTransformer` with lazy `_get_model()` (so health checks don't pay the torch import) and `asyncio.to_thread`-wrapped `embed_profile_fields()` for the request path.
- `profiles/router.py` — `POST /profiles`, `GET /profiles/me`, `PATCH /profiles/me`. Embedding recomputes whenever any of `{age, hometown, college, interests, liked_topics}` changes; handle collisions surface as 409.
- `recommendations/router.py` — derives `source_user_id` from the JWT when present; the query param is now a transitional fallback (returns 400 if neither is provided).
- `pyproject.toml` — adds `PyJWT[crypto]>=2.9`.
- `main.py` — mounts the auth + profiles routers.

## What landed earlier this session — Phase 1.1–1.3 (2026-05-28)

- `apps/api/pyproject.toml` pins `hangpost-matching @ git+https://github.com/ai-bryguy101/hangpost-app@94b15fb` (no PyPI release yet, no tags on the sibling repo) and adds `sentence-transformers>=2.7`.
- `apps/api/src/hangpost_api/matching/engine.py` adapter now delegates to the real export `rank_candidates_with_cold_start` (the stub called a non-existent `rank()`).
- `apps/api/scripts/backfill_embeddings.py` — idempotent batch backfill; embeds `profile_to_text()` output through `all-MiniLM-L6-v2`; checks dim against `EMBEDDING_DIM`.
- `apps/api/src/hangpost_api/recommendations/router.py` — `GET /recommendations`: ST_DWithin pre-filter → load mutuals → engine `UserProfile`s → `rank_candidates_with_cold_start` → log `recommendation_impressions` → return ranked results with `MatchBreakdown`.
- `infra/docker/api.Dockerfile` runtime stage now installs `libgomp1` (torch + lightgbm OpenMP runtime) and copies `apps/api/scripts`.
- Sibling-repo API drift recorded: `UserProfile` has no `name` field and the ranker exports `rank_candidates` / `rank_candidates_with_cold_start`, not `rank` — see `DECISIONS_LOG.md`.

---

## Phase 1 plan (re-sequenced)

The original plan put auth before matching. The revised order leads with the AI story
because the seed corpus is already there:

1. **1.1** Pin `hangpost-matching` in `apps/api/pyproject.toml`. (Needs sibling-repo tag/SHA — see "External inputs needed" below.)
2. **1.2** Write `apps/api/scripts/backfill_embeddings.py` — iterates profiles, calls `hangpost_matching.profile_to_text()`, embeds with `sentence-transformers/all-MiniLM-L6-v2`, writes `embedding` + `bio_synthesized` + `embedding_at`. Idempotent.
3. **1.3** Mount `GET /recommendations`: ST_DWithin pre-filter on `user_locations` → `hangpost_matching.rank()` → log to `recommendation_impressions` → return ranked list with `MatchBreakdown`.
4. **1.4** Clerk JWT middleware + `GET /me`.
5. **1.5** `POST /profiles` + `PATCH /profiles/{me}`.
6. **1.6** On profile write: compute embedding inline (or queue Arq job).

Demoable at the end of 1.3 against synthetic users (no auth needed). End of 1.6 = a real user can sign up and see themselves ranked against the 1,000.

---

## External inputs needed (from operator / sibling repo)

All Phase 1.1–1.3 unknowns resolved on 2026-05-28 by reading the sibling repo directly:

- `hangpost-matching` is **not on PyPI** (no release, no tags, no publish workflow); pinned to commit SHA `94b15fb87099a4f16caf6de0091e8a05460afade`.
- Engine still uses `sentence-transformers/all-MiniLM-L6-v2` (384-dim) — matches `EMBEDDING_DIM`.
- Sibling Dockerfile installs `gcc libgomp1`; mirrored as `libgomp1` in the API runtime stage.
- Public API drift: `UserProfile` has no `name` field (we keep `display_name` on our ORM, never pass it to the engine); top-level ranker is `rank_candidates` / `rank_candidates_with_cold_start`, not `rank`.

Outstanding for later phases: when upstream cuts a `v0.1.0` tag, swap the SHA pin for the tag.

---

## Parallel tracks

- **Design (Vercel + Stitch + Figma)** — produces the mockups Phase 2 will implement against shadcn/ui + Tailwind. See ADR-0005. Operator-driven.
- **ML loop closure** — Phase 7. Logging seam already exists (`recommendation_impressions` + `recommendation_outcomes`).

---

## Session log (most recent first)

### 2026-05-28 — Repo assessment + memory infra
- Did a full Phase 0 review; confirmed scaffolding, schema, CI, seed all green.
- Pushed back on the original Phase 1 plan ("Clerk → cosine `/recommendations`"). Revised to lead with matching-engine pinning + embedding backfill + `/recommendations` against the sibling-repo ranker, then layer Clerk on top. Reason: the synthetic corpus already exists and the resume pitch depends on the sibling-repo ranker, not raw cosine.
- Added `docs/STATUS.md` (this file) and `docs/DECISIONS_LOG.md`.
- Added ADR-0005 (design pipeline = Figma + Stitch → shadcn/ui).
- Updated `CLAUDE.md` §6 phase table with status column.
- No code changes yet. Phase 1 implementation begins next session, after operator confirms sibling-repo pin target.
