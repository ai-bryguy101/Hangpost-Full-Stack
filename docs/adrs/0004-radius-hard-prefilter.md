# ADR 0004: Radius is a hard pre-filter, never a ranking signal

## Status

Accepted — 2026-05-26.

## Context

Hangpost surfaces "nearby strangers you'd statistically get along with."
Two distinct location concepts are easy to conflate:

- **Current GPS location** — where the user physically is right now.
- **Hometown** — a biographical attribute used for matching.

A tempting but wrong design is to feed `distance_km` into the ranker as a
feature so closer people score higher. This corrupts the product: the
audience is *already* defined as "people in my city right now," and once
inside that set, physical proximity says nothing about compatibility.
Distance-as-a-feature also leaks the ranker into the retrieval layer,
making it impossible to reason about either independently.

## Decision

- **Current GPS location** is a hard pre-filter at candidate retrieval:
  `ST_DWithin(geom, ST_MakePoint(:lon,:lat)::geography, :radius_m)`.
  Profiles outside the radius are removed *before* the ranker runs.
  Distance never enters the score.
- **Hometown** is a soft matching signal, weighted by the matching engine
  alongside mutual friends, college, hobbies, and age.

Any proposal to add `distance_km` (or any current-location-derived value)
as a ranker feature is rejected by default; overturning this requires a
superseding ADR.

## Consequences

- Retrieval (PostGIS) and ranking (matching engine) stay cleanly
  separated and independently testable.
- The radius is a tunable product knob, not a learned weight.
- The matching engine needs no notion of current location — it ranks an
  already-local candidate set, exactly as designed.
