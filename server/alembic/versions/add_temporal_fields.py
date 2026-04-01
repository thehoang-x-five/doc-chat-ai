"""Add temporal fields to memori_knowledge_graph

Revision ID: add_temporal_fields
Revises: add_memori_prefs_attrs
Create Date: 2026-01-18

Graphiti-inspired temporal support:
- valid_at: When the fact became true in reality
- invalid_at: When the fact stopped being true in reality  
- expired_at: When the triple was invalidated by a contradiction
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_temporal_fields'
down_revision = 'add_memori_prefs_attrs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add temporal columns to memori_knowledge_graph
    op.add_column(
        'memori_knowledge_graph',
        sa.Column('valid_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'memori_knowledge_graph',
        sa.Column('invalid_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'memori_knowledge_graph',
        sa.Column('expired_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create indexes for efficient temporal queries
    op.create_index(
        'idx_memori_kg_valid_at',
        'memori_knowledge_graph',
        ['valid_at']
    )
    op.create_index(
        'idx_memori_kg_expired_at',
        'memori_knowledge_graph',
        ['expired_at']
    )


def downgrade() -> None:
    op.drop_index('idx_memori_kg_expired_at', table_name='memori_knowledge_graph')
    op.drop_index('idx_memori_kg_valid_at', table_name='memori_knowledge_graph')
    op.drop_column('memori_knowledge_graph', 'expired_at')
    op.drop_column('memori_knowledge_graph', 'invalid_at')
    op.drop_column('memori_knowledge_graph', 'valid_at')
