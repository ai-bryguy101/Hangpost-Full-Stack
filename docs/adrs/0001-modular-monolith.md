# ADR 0001: Modular monolith over microservices for v1

## Status

Accepted — 2026-05-26.

## Context

Hangpost has several bounded contexts (auth, profiles, posts, hangouts,
social, matching, notifications, safety, recommendations). The team is
one engineer. Time-to-first-user matters more than future-team scaling.
Day-one microservices for a solo developer is a red flag, not a senior
signal — distributed systems impose IPC contracts, deployment
choreography, and debugging overhead that buy nothing at this scale.

## Decision

Build a modular monolith in FastAPI. Each bounded context is a Python
package under `apps/api/src/hangpost_api/<domain>/`. Cross-domain calls
go through service-layer functions, never through repository imports from
another domain. The matching engine stays its own pip-installed package
(repo: `hangpost-matching-engine`) so it can be extracted to a sidecar
later without a rewrite.

## Consequences

- One deploy, one runbook, one log stream.
- Refactoring across domains is cheap — no network contracts to version.
- When a single domain needs different scaling, extraction is a known
  pattern: lift the package, wrap it in a thin HTTP/gRPC façade.
- Requires discipline to keep domain boundaries intact (enforced in code
  review; a custom lint rule against cross-domain repository imports is a
  candidate for a future phase).
- `core/` holds only cross-cutting infrastructure (config, db, logging)
  and may never import from a domain package.
