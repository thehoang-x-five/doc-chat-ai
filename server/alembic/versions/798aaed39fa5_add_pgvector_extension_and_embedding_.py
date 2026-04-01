"""add_pgvector_extension_and_embedding_column

Revision ID: 798aaed39fa5
Revises: cdaba46904f0
Create Date: 2026-01-20 19:45:08.977578

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '798aaed39fa5'
down_revision: Union[str, None] = 'cdaba46904f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # Add embedding column to chunks table
    # Using raw SQL because pgvector.sqlalchemy.Vector may not be available at migration time
    op.execute('ALTER TABLE chunks ADD COLUMN embedding vector(768)')
    
    # Create index for vector similarity search (IVFFlat for better performance)
    # This will speed up cosine similarity searches
    op.execute('CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)')


def downgrade() -> None:
    # Drop index first
    op.execute('DROP INDEX IF EXISTS idx_chunks_embedding')
    
    # Drop embedding column
    op.execute('ALTER TABLE chunks DROP COLUMN IF EXISTS embedding')
    
    # Note: We don't drop the extension as other tables might use it
