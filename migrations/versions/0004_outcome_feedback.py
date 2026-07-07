"""Expand outcome memory for follow-up and scoring."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("outcome_memories", sa.Column("actual_choice", sa.String(16), nullable=True))
    op.add_column(
        "outcome_memories",
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
    )
    op.add_column("outcome_memories", sa.Column("follow_up_date", sa.Date(), nullable=True))
    op.add_column(
        "outcome_memories", sa.Column("satisfaction_score", sa.Integer(), nullable=True)
    )
    op.add_column("outcome_memories", sa.Column("regret_score", sa.Integer(), nullable=True))
    op.add_column(
        "outcome_memories", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("outcome_memories", "resolved_at")
    op.drop_column("outcome_memories", "regret_score")
    op.drop_column("outcome_memories", "satisfaction_score")
    op.drop_column("outcome_memories", "follow_up_date")
    op.drop_column("outcome_memories", "status")
    op.drop_column("outcome_memories", "actual_choice")

