# Decisions log

> Running journal of small calls that don't merit a full ADR but are
> worth remembering so we don't re-litigate them. ADRs in `docs/adrs/`
> are for defendable architectural decisions; this file is for everything
> else (tool choices, library picks, off-plan adjustments, open questions
> still in flight).
>
> Append-only. Newest entries on top. Date every entry.

---

## 2026-05-29 — PR A call: location endpoint lives in `profiles`, not its own package

`POST /user-locations` went into `apps/api/.../profiles/locations.py` (a
small router with its own `/user-locations` prefix), not a new top-level
`locations/` package. The `profiles` package already declares ownership
of the `user_locations` table (`profiles/__init__.py`), and a whole
package for one endpoint is premature. The flat `/user-locations` public
path is preserved by giving the router its own prefix rather than nesting
under `/profiles`. Extract a `locations` package only if location history
/ delete / sharing-settings endpoints arrive later.

## 2026-05-29 — Require a location before the `/profile/new` submit

`GET /recommendations` 404s with no profile and 409s with no location.
The onboarding form therefore disables its submit button until "Use my
current location" has succeeded, and creates the location row before the
profile row — so a brand-new user can never land on a `/demo` that
immediately 409s. Belt-and-suspenders: `/demo` also catches 404/409 and
shows an onboarding CTA instead of a raw error. The comma-separated
interests/likes inputs are deliberately minimal (the `/demo` surface is
throwaway scaffolding per the 2026-05-28 entry); the chip picker lands
with the Phase 2 designs.

## 2026-05-29 — Retire the `source_user_id` fallback on `/recommendations`

The transitional crutch logged on 2026-05-28 ("Optional auth on
`/recommendations` is a transitional crutch") is now removed:
`/recommendations` is Clerk-JWT-only. The web sign-up → `/profile/new` →
`/demo` flow means a real signed-in user can be the source, so the
synthetic-corpus query-param path is no longer needed. The seed corpus
is still the *ranking target* (the 1,000 nearby candidates) — we just no
longer impersonate a seed user as the *viewer*.

## 2026-05-29 — Pull ML-loop-closure forward from Phase 7 into "PR B"

CLAUDE.md §6 puts outcome capture in Phase 3 (UI hooks) and the
retraining job in Phase 7. The full retrain stays in Phase 7, but the
**outcome-capture endpoint + offline evaluation harness** move forward
into the next queued PR (PR B in STATUS.md).

Why: CLAUDE.md §10 says every PR should make the resume pitch
stronger. Today the system logs *what it recommended* but never
records *whether the recommendation was good*. Without outcomes there
is literally no ML loop to demonstrate. A recruiter reading the repo
sees an embedding-powered ranker but no evaluation story. Even a thin
outcome write + a single NDCG-vs-baseline report committed to
`docs/eval/` flips that.

Cost: small. Tables exist (`recommendation_outcomes`), the impression
seam is already in `recommendations/router.py`. New surface area is
one POST endpoint, three click handlers on `/demo`, and a `scripts/
evaluate.py`.

This is a sequencing change, not an architectural change — the
destination in CLAUDE.md §6 is unchanged.

---

## 2026-05-29 — Log a feature snapshot alongside every impression

Decision: when `/recommendations` writes a `recommendation_impressions`
row, it should also persist the *raw inputs* the ranker saw
(embedding hash, mutual-friend count, hometown-match bool,
college-match bool, interest-overlap count, candidate count after the
PostGIS pre-filter), not just the `breakdown_json` output.

Why: when Phase 7's `LearnedRanker.fit()` retrains on past queries, it
needs to reconstruct the feature vector that was actually scored, not
just the score. Embeddings drift (profile edits), friend graphs drift
(new accepted friendships), so reading them at retrain time gives
different inputs than the ranker saw at recommend time. Logging the
snapshot at impression time eliminates the silent feature-skew bug
that bites every team that skips this.

Doesn't need a new table — extend `breakdown_json` (it's JSONB) or add
a sibling `features_json` column. Decide in the PR.

---

## 2026-05-28 — Age floor is 18, not 13

Hangpost is positioned as a young-adult product (target ~23; seed
corpus minimum was already 22). Adult-only floor avoids the
COPPA / age-mixed friend-discovery regulatory weight and matches how
the product is being pitched. Enforced at the DB (CHECK constraint
in Alembic `0002`), the Pydantic boundary, and documented here so
future "let's drop the floor to onboard high-schoolers" suggestions
get triaged into an ADR instead of a quiet schema change.

---

## 2026-05-28 — Clerk publishable key passes via Docker build arg, not runtime env

`NEXT_PUBLIC_*` env vars are inlined into the client bundle during
`next build` — they cannot be swapped at runtime in a standalone
Next.js image. So `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is forwarded
through docker-compose's `build.args` and consumed by an `ARG` in
`infra/docker/web.Dockerfile` before `npm run build` runs. The
secret key (`CLERK_SECRET_KEY`) and the API's `CLERK_JWKS_URL` stay
as runtime env vars — they're only read server-side. Changing the
publishable key means rebuilding the web image (`docker compose up
-d --build web`). Documented in `docs/CLERK_SETUP.md`.

---

## 2026-05-28 — `/demo` is intentionally throwaway scaffolding

The web demo page exists to make the Phase-1 ranker clickable in a
browser — not as production UI. No design pass, no Tailwind theme
work, no shared component library. It will be replaced (or deleted)
once the Phase 2 + 3 designs land and the real "Matched daily picks"
surface is built. Keeping it small and ugly on purpose so nobody
mistakes it for the product.

---

## 2026-05-28 — pgvector arrays must be coerced to plain Python floats at the load seam

`Profile.embedding` comes back from pgvector as a `numpy.ndarray`.
Wrapping with `list()` preserves the `numpy.float32` element type,
which leaks through the engine's pure-Python cosine math into
`MatchBreakdown.semantic_similarity`, then crashes `json.dumps` when
SQLAlchemy tries to write the impression's `breakdown_json` into
JSONB. Fix: `[float(x) for x in embedding]` everywhere we load
a vector from the ORM. Caught during the Phase-1 verify pass; would
have shown up the moment any embedding hit production.

---

## 2026-05-28 — CPU-only torch in the API runtime image

The default `torch` wheel on Linux ships with CUDA libs
(`nvidia-cudnn-cu13` etc), which add ~3 GB and fill the Codespace
disk before `pip install ./apps/api` finishes. We have no GPU on
Fly.io or Codespaces, so install torch from the CPU index first
(`pip install --index-url https://download.pytorch.org/whl/cpu
torch`) and `sentence-transformers` then reuses it. Anything that
needs GPU later goes through a different image / runtime, not the
API's default.

---

## 2026-05-28 — Embed-on-write is inline, not Arq

`POST /profiles` and `PATCH /profiles/me` synthesize the bio + encode
the vector inside the request handler (via `asyncio.to_thread` so the
event loop stays free). The matching engine's eventual-consistency
story is fine — a stale embedding is just a slightly stale ranking,
not an error — but inline keeps the demo path obvious: the moment a
user saves their profile, `embedding_at` reflects it. Move to an Arq
job the first time we see a real latency complaint or batch edit.

---

## 2026-05-28 — Optional auth on `/recommendations` is a transitional crutch

The endpoint accepts either a Clerk JWT (preferred) or a
`source_user_id` query param (synthetic-corpus demo path). It is
explicitly a Phase-1 bridge: seed users have no Clerk identity, so the
only way to demo ranking against them today is the query param. The
moment the web frontend ships with Clerk, drop the fallback and make
the endpoint auth-only. Logged in `STATUS.md` "What is intentionally
NOT done yet".

---

## 2026-05-28 — Lazy-load `sentence_transformers` in `profiles.embedder`

The model singleton is loaded inside `_get_model()` rather than at
module top so `pytest tests/test_health.py` (and the docker readiness
probe) don't pay the ~2s torch import. The first profile write takes
~2s extra; every subsequent write is ~50ms. Acceptable trade.

---

## 2026-05-28 — Clerk JWT verification skips audience check

`jwt.decode(..., options={"verify_aud": False})`. Clerk's own backend
SDK leaves `aud` verification off by default and treats the issuer
(Clerk instance domain → JWKS) as the trust anchor. We can tighten
once we move to a production Clerk instance with a known audience id;
documented here so we don't ship a "secure" hardening that breaks the
dev login flow.

---

## 2026-05-28 — Pin `hangpost-matching` to a commit SHA, not a tag

Sibling repo (`ai-bryguy101/hangpost-app`) has no GitHub releases, no
git tags, and no PyPI release. Pinned to commit
`94b15fb87099a4f16caf6de0091e8a05460afade` (default branch HEAD,
"Add pre-deploy smoke test for the HF Space", merged from PR #19).
Less pretty than a tag but reproducible. Swap for a tag the moment
upstream cuts one.

---

## 2026-05-28 — Use the engine's `rank_candidates_with_cold_start`, not `rank`

The Phase 0 stub at `hangpost_api/matching/engine.py` called
`hangpost_matching.rank(source, candidates)`. That function does not
exist in the engine. The actual exports are `rank_candidates` and
`rank_candidates_with_cold_start` (the latter falls back to a
popularity prior for sparse sources, which is exactly the right
behaviour for new users in Phase 1). Adapter now calls the
cold-start-aware variant. `UserProfile` also has no `name` field —
`display_name` is an app-side concern that never enters the engine;
the recommendations router carries it on the response, not the engine
input.

---

## 2026-05-28 — `sentence-transformers` lives in the API package, not an extra

The matching engine exposes a `SentenceTransformerEmbedder` but never
loads a model itself — embeddings are passed in precomputed. We own
the embedding step (backfill script + future inline embed-on-write),
so `sentence-transformers` is a first-class API dependency rather than
an optional extra. Heavier image, but no second deploy path.

---

## 2026-05-28 — Revise Phase 1 sequencing

Original Phase 1 (per `CLAUDE.md` §6): "Auth + Profile". Operator's initial framing
also pulled `/recommendations` into Phase 1.

Decision: lead Phase 1 with **matching engine pinning + embedding backfill on the
1,001 seed profiles + `/recommendations`**, *then* layer Clerk on top.

Reasons:
- The synthetic corpus already exists; we can demo the AI loop today without auth.
- A `/recommendations` endpoint that ranks by raw cosine similarity (skipping the
  sibling-repo `hangpost_matching.rank()`) would directly undermine the resume
  pitch in `CLAUDE.md` §10.
- Clerk + profile create/edit is straightforward once the ranker is live and the
  embedding pipeline exists; doing it first just delays the headline feature.

No ADR because the phase-ordering is a tactical sequence, not an architectural
direction change — the destination is the same as `CLAUDE.md` §6 Phase 1.

---

## 2026-05-28 — Memory file scheme

Adopted three-file scheme that the assistant reads at the start of every session:

- `CLAUDE.md` — principles, vision, decisions (slow-changing).
- `docs/STATUS.md` — current state and session log (updated every session).
- `docs/DECISIONS_LOG.md` — running journal (this file).

ADRs continue to live under `docs/adrs/` for big calls.

---

## Open questions (resolve before the relevant phase starts)

### Sibling repo — needed before going public

- [ ] Sibling repo rename (`hangpost-app` → `hangpost-matching-engine`) — still pending upstream. Affects the git URL we pin.
- [ ] Upstream tag for `hangpost-matching`. Swap the SHA pin for the first tag they cut.

### Design pipeline — needed for Phase 2

- [ ] Where do shared design tokens live? Figma library only, or exported to a JSON file in the repo?
- [ ] Stitch-generated code: commit raw, or hand-translate to shadcn/ui? (Recommendation in ADR-0005: hand-translate.)
