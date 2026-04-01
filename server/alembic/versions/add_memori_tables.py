"""Add Memori-style memory tables

Revision ID: add_memori_tables
Revises: add_processing_progress
Create Date: 2026-01-16

Copied from Memori project for advanced memory management:
- Entity Facts with embeddings for semantic search
- Knowledge Graph (Semantic Triples)
- Session management with timeout
- Process tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_memori_tables'
down_revision = 'add_processing_progress'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create memori_entities table
    op.create_table(
        'memori_entities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id')
    )
    op.create_index('idx_memori_entities_workspace', 'memori_entities', ['workspace_id'])
    op.create_index('idx_memori_entities_external_id', 'memori_entities', ['external_id'])
    
    # Create memori_entity_facts table
    op.create_table(
        'memori_entity_facts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_embedding', sa.LargeBinary(), nullable=True),  # Binary for FAISS
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('importance_score', sa.Float(), default=1.0, nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['memori_entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_entity_facts_entity', 'memori_entity_facts', ['entity_id'])
    op.create_index('idx_memori_entity_facts_importance', 'memori_entity_facts', ['importance_score'])
    
    # Create memori_knowledge_graph table (Semantic Triples)
    op.create_table(
        'memori_knowledge_graph',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('subject_name', sa.String(255), nullable=False),
        sa.Column('subject_type', sa.String(100), nullable=True),
        sa.Column('predicate', sa.String(255), nullable=False),
        sa.Column('object_name', sa.String(255), nullable=False),
        sa.Column('object_type', sa.String(100), nullable=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('confidence', sa.Float(), default=1.0, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['memori_entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_kg_entity', 'memori_knowledge_graph', ['entity_id'])
    op.create_index('idx_memori_kg_subject', 'memori_knowledge_graph', ['subject_name'])
    op.create_index('idx_memori_kg_object', 'memori_knowledge_graph', ['object_name'])
    
    # Create memori_processes table
    op.create_table(
        'memori_processes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id')
    )
    op.create_index('idx_memori_processes_workspace', 'memori_processes', ['workspace_id'])
    op.create_index('idx_memori_processes_external_id', 'memori_processes', ['external_id'])
    
    # Create memori_process_attributes table
    op.create_table(
        'memori_process_attributes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('process_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['process_id'], ['memori_processes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_process_attrs_process', 'memori_process_attributes', ['process_id'])
    
    # Create memori_sessions table
    op.create_table(
        'memori_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('uuid', sa.String(255), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('process_id', sa.Integer(), nullable=True),
        sa.Column('workspace_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['memori_entities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['process_id'], ['memori_processes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid')
    )
    op.create_index('idx_memori_sessions_workspace', 'memori_sessions', ['workspace_id'])
    op.create_index('idx_memori_sessions_last_activity', 'memori_sessions', ['last_activity_at'])
    op.create_index('idx_memori_sessions_uuid', 'memori_sessions', ['uuid'])
    
    # Create memori_conversations table
    op.create_table(
        'memori_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['memori_sessions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_conversations_session', 'memori_conversations', ['session_id'])
    
    # Create memori_conversation_messages table
    op.create_table(
        'memori_conversation_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('message_type', sa.String(50), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['memori_conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_memori_conv_messages_conversation', 'memori_conversation_messages', ['conversation_id'])


def downgrade() -> None:
    op.drop_table('memori_conversation_messages')
    op.drop_table('memori_conversations')
    op.drop_table('memori_sessions')
    op.drop_table('memori_process_attributes')
    op.drop_table('memori_processes')
    op.drop_table('memori_knowledge_graph')
    op.drop_table('memori_entity_facts')
    op.drop_table('memori_entities')
