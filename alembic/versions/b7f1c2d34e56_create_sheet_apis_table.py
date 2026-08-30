"""create sheet_apis table

Revision ID: b7f1c2d34e56
Revises: addc356803d7
Create Date: 2026-08-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f1c2d34e56'
down_revision: Union[str, Sequence[str], None] = 'addc356803d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'sheet_apis',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('spreadsheet_id', sa.String(), nullable=False),
        sa.Column('sheet_name', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'spreadsheet_id', 'sheet_name', name='uq_sheet_api_target'),
    )
    op.create_index(op.f('ix_sheet_apis_user_id'), 'sheet_apis', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_sheet_apis_user_id'), table_name='sheet_apis')
    op.drop_table('sheet_apis')
