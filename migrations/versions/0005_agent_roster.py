"""Persist the selected three-member committee roster."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "decisions",
        sa.Column(
            "agent_roster_json",
            sa.Text(),
            nullable=False,
            server_default='["wallet", "future_me", "chaos"]',
        ),
    )


def downgrade() -> None:
    op.drop_column("decisions", "agent_roster_json")
