"""Add processing progress fields to documents

Revision ID: add_processing_progress
Revises: add_document_categories
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_processing_progress'
down_revision: Union[str, None] = 'add_document_categories'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add processing progress columns to documents table
    op.add_column('documents', sa.Column('processing_progress', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('documents', sa.Column('processing_step', sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'processing_step')
    op.drop_column('documents', 'processing_progress')
