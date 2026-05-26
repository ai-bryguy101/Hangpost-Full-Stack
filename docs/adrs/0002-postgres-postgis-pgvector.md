# ADR 0002: One Postgres for relational, spatial, and vector data

## Status

Accepted — 2026-05-26.

## Context

Hangpost needs three storage capabilities that are often split across
separate systems:

1. Relational data (users, posts, friendships, the social graph).
2. Geospatial queries — the radius pre-filter is literally
   `ST_DWithin(geom, point, radius)`.
3. Vector similarity — profile embeddings for the matching engine.

A common instinct is Postgres + a geo service + a dedicated vector DB
(Pinecone/Weaviate). Each extra datastore adds a network hop, a
consistency boundary, and a vendor.

## Decision

Use a single PostgreSQL 16 instance with the **PostGIS** and **pgvector**
extensions. Locations are `geography(POINT, 4326)` (geodesic, GIST
indexed). Embeddings are `vector(384)` (sentence-transformers MiniLM,
HNSW + cosine indexed). Managed via Neon, which ships both extensions on
its free tier.

`geography` (not `geometry`) is chosen so distance is geodesic from day
one — no flat-earth math when the product goes international.

## Consequences

- Embeddings live next to the rows they describe; no cross-store joins or
  dual-write consistency problems.
- The radius pre-filter is a single indexed query, not an application-side
  Haversine loop that can't use an index.
- Backups, transactions, and migrations cover all three data shapes at
  once.
- Ceiling: a dedicated vector DB outperforms pgvector at very large
  scale. Revisit only if recall/latency at our embedding volume becomes a
  measured problem — not before.
