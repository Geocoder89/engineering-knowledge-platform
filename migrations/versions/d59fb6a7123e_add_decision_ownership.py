"""add decision ownership

Revision ID: d59fb6a7123e
Revises: 8962e9baed2e
Create Date: 2026-09-20 21:39:13.973895

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d59fb6a7123e"
down_revision: Union[str, Sequence[str], None] = "8962e9baed2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add required decision ownership."""

    op.add_column(
        "decisions",
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    decision_count = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM decisions",
        ),
    )

    if decision_count:
        raise RuntimeError(
            "Cannot add required decision ownership while existing decisions "
            "have no owner. Assign an owner to every decision before retrying.",
        )

    op.alter_column(
        "decisions",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_index(
        "ix_decisions_owner_user_id",
        "decisions",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_decisions_owner_user_id_users",
        "decisions",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove decision ownership."""

    op.drop_constraint(
        "fk_decisions_owner_user_id_users",
        "decisions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_decisions_owner_user_id",
        table_name="decisions",
    )
    op.drop_column(
        "decisions",
        "owner_user_id",
    )
