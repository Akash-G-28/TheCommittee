"""Add minimal outcome memory for MCP tools."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outcome_memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("decisions.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("actual_action", sa.String(500), nullable=False),
        sa.Column("reflection", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outcome_memories")

