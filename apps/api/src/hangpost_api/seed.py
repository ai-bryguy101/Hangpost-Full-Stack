"""Seed the database with synthetic profiles for local development.

Run it as a module from ``apps/api``::

    python -m hangpost_api.seed

What it does, in plain terms:

1. Reads the synthetic CSV at ``apps/api/seeds/test_profiles.csv``.
2. For each row, creates (or updates) one ``users`` row and one
   ``profiles`` row whose fields line up with the matching engine's
   ``UserProfile`` (interests, liked_topics, hometown, college, age).
3. Gives each user a ``user_locations`` point scattered randomly across
   Washington DC. The app is location-based: a viewer only ever sees
   people inside their current radius (an ``ST_DWithin`` pre-filter),
   so the whole synthetic population lives in one city or the feed
   would come back empty.

The script is idempotent. Each CSV row maps to a fixed synthetic
identity (``auth_sub = "seed-00042"``), so re-running updates the same
rows instead of creating duplicates. Locations are generated from a
seeded RNG keyed by row index, so they stay put across re-runs too.

Embeddings and ``bio_synthesized`` are left NULL on purpose: they come
from the matching engine and get backfilled in Phase 3.
"""

import asyncio
import csv
import math
import random
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from hangpost_api.auth.models import User
from hangpost_api.core.db import SessionFactory
from hangpost_api.profiles.models import Profile, UserLocation

# Default fixture path: apps/api/seeds/test_profiles.csv, resolved
# relative to this file so it works regardless of the current directory.
DEFAULT_CSV = Path(__file__).resolve().parents[2] / "seeds" / "test_profiles.csv"

# All synthetic users live in Washington DC. (lat, lon) of the city center.
DC_CENTER_LAT = 38.9072
DC_CENTER_LON = -77.0369
# Maximum scatter radius from the center, in meters (~9 km covers the District).
SCATTER_RADIUS_M = 9_000

# Marks rows this script owns, so re-runs target them and nothing else.
AUTH_PROVIDER = "seed"


def _split_list(raw: str) -> list[str]:
    """Turn a ``"a; b; c"`` cell into ``["a", "b", "c"]`` (blanks dropped)."""
    return [item.strip() for item in raw.split(";") if item.strip()]


def _dedupe(items: list[str]) -> list[str]:
    """Drop duplicates while preserving first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _scatter_point(rng: random.Random) -> tuple[float, float]:
    """Return a (lon, lat) point uniformly distributed over a DC-sized disk.

    ``sqrt(random)`` makes points spread evenly by area rather than
    clumping near the center. Meter offsets are converted to degrees
    using the local scale (longitude shrinks by ``cos(latitude)``).
    """
    distance_m = SCATTER_RADIUS_M * math.sqrt(rng.random())
    bearing = rng.uniform(0, 2 * math.pi)
    north_m = distance_m * math.cos(bearing)
    east_m = distance_m * math.sin(bearing)

    lat = DC_CENTER_LAT + (north_m / 111_320)
    lon = DC_CENTER_LON + (east_m / (111_320 * math.cos(math.radians(DC_CENTER_LAT))))
    return lon, lat


def _handle_from_name(name: str, index: int) -> str:
    """Build a unique, URL-safe handle like ``aria_patel_0042``."""
    slug = "".join(ch if ch.isalnum() else "_" for ch in name.strip().casefold())
    slug = "_".join(filter(None, slug.split("_")))
    return f"{slug}_{index:04d}"


async def seed(csv_path: Path) -> None:
    """Load every row of ``csv_path`` into users/profiles/user_locations."""
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    async with SessionFactory() as session:
        for index, row in enumerate(rows):
            auth_sub = f"seed-{index:05d}"
            email = f"{auth_sub}@hangpost.test"

            # 1) Upsert the identity row, keyed by (auth_provider, auth_sub).
            user_stmt = (
                insert(User)
                .values(auth_provider=AUTH_PROVIDER, auth_sub=auth_sub, email=email)
                .on_conflict_do_update(
                    index_elements=[User.auth_provider, User.auth_sub],
                    set_={"email": email},
                )
                .returning(User.id)
            )
            user_id = (await session.execute(user_stmt)).scalar_one()

            interests = _split_list(
                row["hobbies_activities_sports_games_skills_certifications"]
            )
            # The engine's liked_topics bucket is "likes/preferences": the
            # CSV splits that across interests_likes and fan_of, so we merge.
            liked_topics = _dedupe(
                _split_list(row["interests_likes"]) + _split_list(row["fan_of"])
            )

            # 2) Upsert the profile, keyed by user_id.
            profile_stmt = insert(Profile).values(
                user_id=user_id,
                display_name=row["name"].strip(),
                handle=_handle_from_name(row["name"], index),
                age=int(row["age"]),
                hometown=row["hometown"].strip() or None,
                college=row["college"].strip() or None,
                interests=interests,
                liked_topics=liked_topics,
            )
            await session.execute(
                profile_stmt.on_conflict_do_update(
                    index_elements=[Profile.user_id],
                    set_={
                        "display_name": profile_stmt.excluded.display_name,
                        "handle": profile_stmt.excluded.handle,
                        "age": profile_stmt.excluded.age,
                        "hometown": profile_stmt.excluded.hometown,
                        "college": profile_stmt.excluded.college,
                        "interests": profile_stmt.excluded.interests,
                        "liked_topics": profile_stmt.excluded.liked_topics,
                    },
                )
            )

            # 3) Upsert the DC location. Seeding the RNG per row keeps the
            # point stable across re-runs.
            lon, lat = _scatter_point(random.Random(f"loc-{index}"))
            location_stmt = insert(UserLocation).values(
                user_id=user_id,
                geom=f"SRID=4326;POINT({lon} {lat})",
                accuracy_m=25,
            )
            await session.execute(
                location_stmt.on_conflict_do_update(
                    index_elements=[UserLocation.user_id],
                    set_={
                        "geom": location_stmt.excluded.geom,
                        "accuracy_m": location_stmt.excluded.accuracy_m,
                        "updated_at": func.now(),
                    },
                )
            )

        await session.commit()

        total = (await session.execute(select(func.count(Profile.user_id)))).scalar_one()

    print(f"Seeded {len(rows)} rows from {csv_path.name}. profiles total: {total}")


def main() -> None:
    """Entry point: optional CLI arg overrides the default CSV path."""
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")
    asyncio.run(seed(csv_path))


if __name__ == "__main__":
    main()
