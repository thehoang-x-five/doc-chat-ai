"""
Fix database transaction issues.

This script:
1. Checks if all required tables exist
2. Creates missing tables
3. Verifies database connectivity

Run this if you encounter "InFailedSQLTransactionError" errors.

Usage:
    python fix_db_transaction.py
"""
import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


async def main():
    """Main function to fix database issues."""
    sys.path.insert(0, '.')
    
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import settings
    
    logger.info("Connecting to database...")
    # Use database_url property (lowercase)
    db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, echo=False)
    
    async with engine.begin() as conn:
        # 1. Check database connectivity
        logger.info("Testing database connectivity...")
        result = await conn.execute(text("SELECT 1"))
        if result.fetchone():
            logger.info("✓ Database connection OK")
        
        # 2. Check required tables
        required_tables = [
            'users',
            'workspaces',
            'workspace_users',
            'documents',
            'document_versions',
            'chunks',
            'conversations',
            'messages',
            'citations',
            'ai_usage',
            'conversation_summaries',
            'document_categories',
        ]
        
        logger.info("\nChecking required tables...")
        missing_tables = []
        
        for table in required_tables:
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """))
            exists = result.fetchone()[0]
            if exists:
                logger.info(f"  ✓ {table}")
            else:
                logger.warning(f"  ✗ {table} - MISSING")
                missing_tables.append(table)
        
        # 3. Create missing tables
        if missing_tables:
            logger.info(f"\nCreating {len(missing_tables)} missing tables...")
            
            if 'conversation_summaries' in missing_tables:
                logger.info("  Creating conversation_summaries...")
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS conversation_summaries (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        summary_text TEXT NOT NULL,
                        messages_summarized INTEGER NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_conversation_summaries_conversation 
                    ON conversation_summaries(conversation_id)
                """))
                logger.info("  ✓ conversation_summaries created")
            
            if 'document_categories' in missing_tables:
                logger.info("  Creating document_categories...")
                await conn.execute(text("""
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
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_category_workspace 
                    ON document_categories(workspace_id)
                """))
                logger.info("  ✓ document_categories created")
        
        # 4. Add missing columns to documents table
        logger.info("\nChecking documents table columns...")
        
        columns_to_add = [
            ('category_id', 'UUID REFERENCES document_categories(id) ON DELETE SET NULL'),
            ('content_summary', 'TEXT'),
            ('main_headings', "VARCHAR[] DEFAULT '{}'"),
        ]
        
        for col_name, col_type in columns_to_add:
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = '{col_name}'
                )
            """))
            exists = result.fetchone()[0]
            if exists:
                logger.info(f"  ✓ documents.{col_name}")
            else:
                logger.info(f"  Adding documents.{col_name}...")
                await conn.execute(text(f"""
                    ALTER TABLE documents ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                """))
                logger.info(f"  ✓ documents.{col_name} added")
        
        # 5. Create index for category_id if not exists
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id)
        """))
        
        await conn.commit()
    
    await engine.dispose()
    
    logger.info("\n" + "="*50)
    logger.info("✅ Database check/fix completed!")
    logger.info("="*50)
    logger.info("\nIf you still see transaction errors, try:")
    logger.info("1. Restart the server")
    logger.info("2. Run: python -m alembic upgrade head")
    logger.info("3. Check PostgreSQL logs for more details")


if __name__ == "__main__":
    asyncio.run(main())
c