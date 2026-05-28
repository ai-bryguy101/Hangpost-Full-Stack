# Decisions log

> Running journal of small calls that don't merit a full ADR but are
> worth remembering so we don't re-litigate them. ADRs in `docs/adrs/`
> are for defendable architectural decisions; this file is for everything
> else (tool choices, library picks, off-plan adjustments, open questions
> still in flight).
>
> Append-only. Newest entries on top. Date every entry.

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

### Sibling repo (`ai-bryguy101/hangpost-app`) — needed for Phase 1.1

- [ ] Is `hangpost-matching` on **PyPI**, or do we install from a **git tag** (`pip install hangpost-matching @ git+https://github.com/ai-bryguy101/hangpost-app@<tag>`)?
- [ ] Confirmed **release tag or commit SHA** to pin.
- [ ] Public API still includes: `UserProfile`, `Query`, `rank(source, candidates) -> list[Candidate]`, `profile_to_text(profile) -> str`, `LearnedRanker.fit(queries)`, `MatchBreakdown`?
- [ ] Embedding model: is `sentence-transformers/all-MiniLM-L6-v2` (384-dim) still the engine's choice? `apps/api/src/hangpost_api/profiles/models.py:23` is pinned to 384.
- [ ] Is the engine pip-installable on Python 3.12 (matching CI)? Any system deps (e.g. `libgomp`) the API Dockerfile needs?
- [ ] Repo rename status — `hangpost-app` → `hangpost-matching-engine` (mentioned in `CLAUDE.md` header). Affects the git URL we pin.

### Design pipeline — needed for Phase 2

- [ ] Where do shared design tokens live? Figma library only, or exported to a JSON file in the repo?
- [ ] Stitch-generated code: do we want to commit it raw, or hand-translate to shadcn/ui? (Recommendation in ADR-0005: hand-translate.)
