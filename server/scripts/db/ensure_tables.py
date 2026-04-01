"""
Ensure all required tables exist in the database.
Run this script after migration to verify and create missing tables.

Usage:
    python ensure_tables.py
"""
import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# SQL to create conversation_summaries table if not exists
CREATE_CONVERSATION_SUMMARIES = """
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    messages_summarized INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_conversation 
ON conversation_summaries(conversation_id);
"""

# SQL to create document_categories table if not exists
CREATE_DOCUMENT_CATEGORIES = """
CREATE TABLE IF NOT EXISTS document_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL,
    description TEXT,
    content_summary TEXT,
    keywords VARCHAR[] DEFAULT '{}',
    icon VARCHAR(50),
    color VARCHAR(20),
    display_order INTEGER DEFAULT 0,
    is_auto_generated BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_category_workspace_slug UNIQUE (workspace_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_category_workspace ON document_categories(workspace_id);
"""

# SQL to add category_id to documents if not exists
ADD_CATEGORY_TO_DOCUMENTS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'category_id'
    ) THEN
        ALTER TABLE documents ADD COLUMN category_id UUID REFERENCES document_categories(id) ON DELETE SET NULL;
        CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'content_summary'
    ) THEN
        ALTER TABLE documents ADD COLUMN content_summary TEXT;
    END IF;
    
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'documents' AND column_name = 'main_headings'
    ) THEN
        ALTER TABLE documents ADD COLUMN main_headings VARCHAR[] DEFAULT '{}';
    END IF;
END $$;
"""


async def check_table_exists(conn, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = await conn.execute(text(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = '{table_name}'
        )
    """))
    row = result.fetchone()
    return row[0] if row else False


async def ensure_tables():
    """Ensure all required tables exist."""
    # Import settings
    import sys
    sys.path.insert(0, '.')
    from app.core.config import settings
    
    # Create engine
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Check and create conversation_summaries
        exists = await check_table_exists(conn, 'conversation_summaries')
        if exists:
            logger.info("✓ Table 'conversation_summaries' already exists")
        else:
            logger.info("Creating table 'conversation_summaries'...")
            await conn.execute(text(CREATE_CONVERSATION_SUMMARIES))
            logger.info("✓ Table 'conversation_summaries' created")
        
        # Check and create document_categories
        exists = await check_table_exists(conn, 'document_categories')
        if exists:
            logger.info("✓ Table 'document_categories' already exists")
        else:
            logger.info("Creating table 'document_categories'...")
            await conn.execute(text(CREATE_DOCUMENT_CATEGORIES))
            logger.info("✓ Table 'document_categories' created")
        
        # Add category columns to documents
        logger.info("Ensuring documents table has category columns...")
        await conn.execute(text(ADD_CATEGORY_TO_DOCUMENTS))
        logger.info("✓ Documents table updated")
        
        # Commit changes
        await conn.commit()
    
    await engine.dispose()
    logger.info("\n✅ All tables verified/created successfully!")


if __name__ == "__main__":
    asyncio.run(ensure_tables())
