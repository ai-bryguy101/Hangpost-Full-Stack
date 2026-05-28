# ADR 0005 — Design pipeline: Figma + Stitch → shadcn/ui

- Status: Accepted
- Date: 2026-05-28

## Context

The operator works browser-only (`CLAUDE.md` §1) and is producing visual
mockups in **Figma** and **Stitch** (Google's AI design tool). Phase 2
("Location + Feed MVP") implements the first real UI, so we need a
stated pipeline from mockup → shipped component.

The frontend stack is fixed (`CLAUDE.md` §3): Next.js 15 + Tailwind v4 +
shadcn/ui. Stitch in particular can export code (HTML/CSS/React), which
raises the question of whether to commit that output verbatim or
hand-translate.

## Decision

1. **Figma** is the canonical source of visual truth: layouts,
   component states, design tokens (color, spacing, radius, type scale).
   Tokens are exported from Figma to `apps/web/src/lib/design-tokens.ts`
   (or equivalent) when stable. No binary Figma files are committed.
2. **Stitch** is used as an exploratory and AI-assist tool for early
   mockups. Its exported code is **not** committed directly.
3. **Hand-translation to shadcn/ui + Tailwind** is the only path code
   takes into `apps/web/`. Reasons: design-tool output drifts from our
   component library, ships dead CSS, and hides accessibility regressions.
4. **Vercel** hosts `apps/web/` as already specified (`CLAUDE.md` §3).
   Preview deployments per PR provide the visual review loop.

## Consequences

- A small per-screen tax: every Figma frame needs a `apps/web/src/components/...`
  hand-translation step. We accept this in exchange for a consistent,
  accessible, monolithic component library.
- Design and backend can run in parallel. Backend Phase 1 (auth,
  profile, embeddings, `/recommendations`) does not block on visuals.
- If the operator finds Stitch's React export close enough to shadcn
  patterns to be worth committing, that's a future ADR amendment, not
  a silent override.

## Alternatives considered

- **Commit Stitch output as the source of truth.** Rejected: locks us
  into whatever Stitch happens to generate, fights shadcn/ui patterns,
  and produces components our designers can't refactor confidently.
- **Skip Figma; design in code.** Rejected: the operator's workflow is
  visual-first, and ad-hoc design produces inconsistent type/spacing.
- **Use a third tool (e.g., Penpot, Framer) as the canonical source.**
  Rejected: Figma is already in use and is the industry standard the
  resume pitch in `CLAUDE.md` §10 benefits from.
