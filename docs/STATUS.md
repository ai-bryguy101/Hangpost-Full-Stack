# Hangpost — Status

> **Read at the start of every session.** This file tracks *where we are*.
> `CLAUDE.md` tracks *what we decided*. ADRs track *why*. This file is the
> running ledger of progress and is updated at the **end** of every session,
> in the same commit as the work.

Last updated: **2026-05-28**
Active branch: `claude/repo-assessment-phase-1-y3OKg`
Current phase: **Phase 0 complete → preparing Phase 1**

---

## Phase status (mirrors `CLAUDE.md` §6)

| Phase | Status | Notes |
|---|---|---|
| 0. Foundation | ✅ done | Schema, ORM, seed (1,001 DC profiles), CI, ADRs 0001–0004 |
| 1. Auth + Profile + Embeddings + `/recommendations` | 🟡 next | See "Phase 1 plan" below |
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

- `hangpost-matching` is **not pinned** in `apps/api/pyproject.toml` — line 28 is commented out. Phase 1 unblocks this.
- All 1,001 seed profiles have `embedding = NULL` and `bio_synthesized = NULL`. Phase 1 backfills.
- No domain routers wired; `main.py` only exposes `/health` + `/health/ready`.
- No Clerk JWT verification (only the `clerk_jwks_url` settings stub).
- Frontend (`apps/web`) is one health-check landing page. Real UI waits on Phase 2 + Figma designs.

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

To unblock Phase 1 step 1.1, I need to know about the sibling repo `ai-bryguy101/hangpost-app`:

- Is `hangpost-matching` published to **PyPI** yet, or do we install from a **git tag**?
- The **release tag or commit SHA** we should pin to.
- Public entry points we will rely on: `UserProfile`, `Query`, `rank()`, `profile_to_text()`, `LearnedRanker`, `MatchBreakdown`. Confirm signatures haven't drifted from `CLAUDE.md` §5.
- Embedding model used by the engine — is `sentence-transformers/all-MiniLM-L6-v2` still the canonical choice (matches `EMBEDDING_DIM = 384` in `apps/api/src/hangpost_api/profiles/models.py:23`)?

See `docs/DECISIONS_LOG.md` "Open questions" for the full list.

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
