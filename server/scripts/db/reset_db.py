"""Reset database and run migrations from scratch."""
import asyncio
from sqlalchemy import text
from app.db.session import async_engine


async def reset_db():
    print("Dropping all tables...")
    async with async_engine.begin() as conn:
        # Drop all tables in cascade
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    print("All tables dropped!")
    
    # Now run migrations
    print("\nRunning migrations...")
    import sys
    sys.path.insert(0, r'..\.venv\Lib\site-packages')
    from alembic.config import Config
    from alembic import command
    
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    print("\nMigration completed successfully!")


if __name__ == "__main__":
    asyncio.run(reset_db())
