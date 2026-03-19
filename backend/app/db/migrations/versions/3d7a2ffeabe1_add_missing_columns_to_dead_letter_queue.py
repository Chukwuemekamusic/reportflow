"""add missing columns to dead_letter_queue

Revision ID: 3d7a2ffeabe1
Revises: 4557ab7c1468
Create Date: 2026-03-17 21:58:19.289187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d7a2ffeabe1'
down_revision: Union[str, Sequence[str], None] = '4557ab7c1468'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add resolved_at and created_at columns to dead_letter_queue table."""
    op.add_column(
        'dead_letter_queue',
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True), nullable=True)
    )
    op.add_column(
        'dead_letter_queue',
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )


def downgrade() -> None:
    """Remove resolved_at and created_at columns from dead_letter_queue table."""
    op.drop_column('dead_letter_queue', 'created_at')
    op.drop_column('dead_letter_queue', 'resolved_at')
