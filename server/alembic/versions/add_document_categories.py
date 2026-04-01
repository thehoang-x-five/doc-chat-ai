"""Add document categories

Revision ID: add_document_categories
Revises: 5da3eb5bca07
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'add_document_categories'
down_revision: Union[str, None] = '5da3eb5bca07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create document_categories table
    op.create_table(
        'document_categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content_summary', sa.Text(), nullable=True),
        sa.Column('keywords', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('color', sa.String(20), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_auto_generated', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'slug', name='uq_category_workspace_slug')
    )
    op.create_index('idx_category_workspace', 'document_categories', ['workspace_id'])
    
    # Add new columns to documents table
    op.add_column('documents', sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('documents', sa.Column('content_summary', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('main_headings', postgresql.ARRAY(sa.String()), nullable=True, server_default='{}'))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_documents_category',
        'documents', 'document_categories',
        ['category_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Add index for category_id
    op.create_index('idx_documents_category', 'documents', ['category_id'])


def downgrade() -> None:
    # Remove index and foreign key from documents
    op.drop_index('idx_documents_category', table_name='documents')
    op.drop_constraint('fk_documents_category', 'documents', type_='foreignkey')
    
    # Remove columns from documents
    op.drop_column('documents', 'main_headings')
    op.drop_column('documents', 'content_summary')
    op.drop_column('documents', 'category_id')
    
    # Drop document_categories table
    op.drop_index('idx_category_workspace', table_name='document_categories')
    op.drop_table('document_categories')
