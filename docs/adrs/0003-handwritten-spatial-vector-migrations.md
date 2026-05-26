# ADR 0003: Hand-written migrations for spatial and vector DDL

## Status

Accepted — 2026-05-26.

## Context

Alembic autogenerate compares ORM metadata against the live database to
emit migrations. It does not round-trip cleanly for the types Hangpost
relies on:

- PostGIS `geography(POINT, 4326)` columns and GIST indexes.
- pgvector `vector(384)` columns and HNSW indexes with operator classes
  (`vector_cosine_ops`).
- `CREATE EXTENSION` statements (pgcrypto, citext, postgis, vector).
- Functional indexes such as `lower(hometown)` and partial indexes such
  as `WHERE read_at IS NULL`.

Autogenerate either drops these, mis-types them, or proposes spurious
diffs on every run.

## Decision

The initial migration (`0001_initial_schema.py`) is hand-written and
executes explicit DDL via `op.execute`. `docs/SCHEMA.sql` is the
human-readable canonical reference and is kept in lockstep with the
migration by hand. The SQLAlchemy ORM models exist for the application
layer; they are not the migration source of truth.

## Consequences

- Extensions, geography/vector columns, and HNSW/GIST/partial indexes are
  created exactly as intended and verified against PostGIS.
- Two artifacts (migration + `SCHEMA.sql`) must be updated together when
  the schema changes; reviewers check both.
- Autogenerate may still be used as a *drafting aid* for plain relational
  changes, but every generated migration is reviewed and hand-corrected
  for the special types before merge.
