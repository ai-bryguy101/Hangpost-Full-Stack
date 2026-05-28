"""Backfill ``bio_synthesized`` + ``embedding`` for every profile.

Run as a module from ``apps/api``::

    python -m scripts.backfill_embeddings           # only rows missing an embedding
    python -m scripts.backfill_embeddings --force   # re-embed every row

What it does:

1. Loads every ``profiles`` row whose ``embedding`` is NULL, whose
   ``embedding_at`` is older than ``updated_at`` (i.e. the structured
   fields were edited after the last embed), or — with ``--force`` —
   every row.
2. Builds a :class:`hangpost_matching.UserProfile` from each row and
   asks :func:`hangpost_matching.profile_to_text` for a deterministic
   synthesized bio.
3. Encodes every bio in a single batch through
   ``sentence-transformers/all-MiniLM-L6-v2`` (the model the engine
   documents and the dimension the schema is locked to —
   :data:`hangpost_api.profiles.models.EMBEDDING_DIM`).
4. Writes back ``bio_synthesized``, ``embedding``, and
   ``embedding_at = now()``.

The script is idempotent: a clean run with no eligible rows is a no-op
that returns 0. Re-running after a profile edit picks up only the
edited rows.
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

from hangpost_matching import UserProfile, profile_to_text
from sentence_transformers import SentenceTransformer
from sqlalchemy import or_, select, update

from hangpost_api.core.db import SessionFactory
from hangpost_api.profiles.models import EMBEDDING_DIM, Profile

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Encode in chunks so a 1k-row corpus doesn't try to fit one giant tensor
# into memory on tiny boxes. 64 is well under any sensible RAM ceiling.
BATCH_SIZE = 64


def _build_engine_profile(row: Profile) -> UserProfile:
    """Convert a Profile ORM row into the engine's frozen dataclass.

    ``interests`` and ``liked_topics`` come back from Postgres as lists;
    the engine's overlap math wants sets, so we coerce here. Mutual
    friends are intentionally not loaded — the backfill embeds a profile
    in isolation; the social graph only matters at ranking time.
    """
    return UserProfile(
        user_id=str(row.user_id),
        interests=set(row.interests or []),
        liked_topics=set(row.liked_topics or []),
        hometown=row.hometown,
        college=row.college,
        age=row.age,
    )


async def backfill(force: bool) -> int:
    """Embed every eligible profile. Returns the number of rows updated."""
    async with SessionFactory() as session:
        stmt = select(Profile)
        if not force:
            stmt = stmt.where(
                or_(
                    Profile.embedding.is_(None),
                    Profile.embedding_at.is_(None),
                    Profile.embedding_at < Profile.updated_at,
                )
            )
        rows: Sequence[Profile] = (await session.execute(stmt)).scalars().all()

        # Build (row, text) pairs in lockstep so the batch encode result
        # aligns 1:1 with the rows we'll update.
        pairs: list[tuple[Profile, str]] = []
        for row in rows:
            text = profile_to_text(_build_engine_profile(row))
            if text:
                pairs.append((row, text))

        if not pairs:
            print("No profiles needed backfill.")
            return 0

        print(f"Embedding {len(pairs)} profiles with {EMBEDDING_MODEL}...")
        model = SentenceTransformer(EMBEDDING_MODEL)

        # show_progress_bar trips up CI logs; keep it off here, the print()
        # bookends are enough signal for a manual run.
        vectors = model.encode(
            [text for _, text in pairs],
            batch_size=BATCH_SIZE,
            show_progress_bar=False,
        )

        now = datetime.now(UTC)
        for (row, text), vector in zip(pairs, vectors, strict=True):
            embedding = [float(x) for x in vector]
            if len(embedding) != EMBEDDING_DIM:
                raise RuntimeError(
                    f"Embedding dim {len(embedding)} != schema dim {EMBEDDING_DIM}. "
                    f"Did the engine switch models?"
                )
            await session.execute(
                update(Profile)
                .where(Profile.user_id == row.user_id)
                .values(
                    bio_synthesized=text,
                    embedding=embedding,
                    embedding_at=now,
                )
            )

        await session.commit()
        print(f"Backfilled {len(pairs)} profiles.")
        return len(pairs)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed every profile, not just rows missing an embedding.",
    )
    args = parser.parse_args()
    asyncio.run(backfill(force=args.force))


if __name__ == "__main__":
    main()
