"""Add Memori Preferences and Attributes tables

Revision ID: add_memori_prefs_attrs
Revises: add_memori_tables
Create Date: 2025-01-17

Phase 2 of Memori Enhancement:
- Entity Preferences (UI, language, format preferences)
- Entity Attributes (role, skills, location, etc.)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_memori_prefs_attrs'
down_revision = 'add_memori_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create memori_entity_preferences table
    op.create_table(
        'memori_entity_preferences',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),  # ui, language, format, etc.
        sa.Column('preference_key', sa.String(100), nullable=False),
        sa.Column('preference_value', sa.Text(), nullable=False),
        sa.Column('importance_score', sa.Float(), server_default='8.0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['memori_entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_preferences_entity_id', 'memori_entity_preferences', ['entity_id'])
    op.create_index('idx_memori_preferences_category', 'memori_entity_preferences', ['category'])
    op.create_index('idx_memori_preferences_key', 'memori_entity_preferences', ['preference_key'])
    
    # Create memori_entity_attributes table
    op.create_table(
        'memori_entity_attributes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),  # role, skill, location, etc.
        sa.Column('attribute_key', sa.String(100), nullable=False),
        sa.Column('attribute_value', sa.Text(), nullable=False),
        sa.Column('importance_score', sa.Float(), server_default='7.0', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['memori_entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_attributes_entity_id', 'memori_entity_attributes', ['entity_id'])
    op.create_index('idx_memori_attributes_category', 'memori_entity_attributes', ['category'])
    op.create_index('idx_memori_attributes_key', 'memori_entity_attributes', ['attribute_key'])


def downgrade() -> None:
    op.drop_table('memori_entity_attributes')
    op.drop_table('memori_entity_preferences')
