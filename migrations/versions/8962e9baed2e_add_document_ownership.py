"""add document ownership

Revision ID: 8962e9baed2e
Revises: 0bbb364975d6
Create Date: 2026-09-20 00:32:57.261047
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8962e9baed2e"
down_revision: Union[str, Sequence[str], None] = "0bbb364975d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add required document ownership."""

    op.add_column(
        "documents",
        sa.Column(
            "owner_user_id",
            sa.Uuid(),
            nullable=True,
        ),
    )

    document_count = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM documents",
        ),
    )

    if document_count:
        raise RuntimeError(
            "Cannot add required document ownership while existing documents "
            "have no owner. Assign an owner to every document before retrying.",
        )

    op.alter_column(
        "documents",
        "owner_user_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_index(
        "ix_documents_owner_user_id",
        "documents",
        ["owner_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_documents_owner_user_id_users",
        "documents",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Remove document ownership."""

    op.drop_constraint(
        "fk_documents_owner_user_id_users",
        "documents",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_documents_owner_user_id",
        table_name="documents",
    )
    op.drop_column(
        "documents",
        "owner_user_id",
    )
