"""Check if tables exist in database."""
import asyncio
from sqlalchemy import text
from app.db.session import async_engine


async def check_table():
    async with async_engine.connect() as conn:
        for table_name in ['conversation_summaries', 'document_categories']:
            result = await conn.execute(text(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = '{table_name}'
            """))
            rows = result.fetchall()
            if rows:
                print(f"✓ Table '{table_name}' EXISTS")
            else:
                print(f"✗ Table '{table_name}' does NOT exist")
                print("  Run: python -m alembic upgrade head")


if __name__ == "__main__":
    asyncio.run(check_table())


if __name__ == "__main__":
    asyncio.run(check_table())
