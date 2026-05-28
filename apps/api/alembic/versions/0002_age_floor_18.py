"""Raise the profiles age floor from 13 to 18.

Hangpost is positioned as a young-adult social product (target
demographic ~23). Adults-only floor avoids the regulatory weight that
COPPA / age-mixed friend-discovery products carry.

Existing rows are all >= 18 in the seed corpus, so this is a no-op
data-wise — strictly a constraint tightening.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-28
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_age_check")
    op.execute(
        "ALTER TABLE profiles ADD CONSTRAINT profiles_age_check "
        "CHECK (age BETWEEN 18 AND 120)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE profiles DROP CONSTRAINT IF EXISTS profiles_age_check")
    op.execute(
        "ALTER TABLE profiles ADD CONSTRAINT profiles_age_check "
        "CHECK (age BETWEEN 13 AND 120)"
    )
