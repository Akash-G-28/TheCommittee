"""Add durable debate rounds and revised opinions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "debate_rounds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "decision_id", "round_number", name="uq_debate_round_decision_number"
        ),
    )
    op.create_table(
        "revised_opinions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decisions.id"), nullable=False),
        sa.Column("agent", sa.String(32), nullable=False),
        sa.Column("original_vote", sa.String(16), nullable=False),
        sa.Column("vote", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("rebuttal", sa.Text(), nullable=False),
        sa.Column("evidence_that_would_change", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("decision_id", "agent", name="uq_revision_decision_agent"),
    )


def downgrade() -> None:
    op.drop_table("revised_opinions")
    op.drop_table("debate_rounds")

