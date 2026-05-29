"""Add features_json snapshot to recommendation_impressions.

Stores the raw ranker inputs (candidate-pool size, embedding presence,
mutual-friend count, hometown/college match, interest/liked overlap
counts) at impression time so the offline trainer can replay history
without re-reading profiles or the friend graph, which may have drifted
since (DECISIONS_LOG 2026-05-29). Distinct from breakdown_json, which is
the ranker's *output*.

Nullable: impressions logged before this migration have no snapshot.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE recommendation_impressions ADD COLUMN features_json JSONB")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE recommendation_impressions DROP COLUMN IF EXISTS features_json"
    )
