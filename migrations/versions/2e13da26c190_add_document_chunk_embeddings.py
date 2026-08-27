"""add document chunk embeddings

Revision ID: 2e13da26c190
Revises: 4b1b119fa8ab
Create Date: 2026-08-25 21:19:17.705188

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "2e13da26c190"
down_revision: str | Sequence[str] | None = "4b1b119fa8ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column(
        "document_chunks",
        "embedding",
    )
