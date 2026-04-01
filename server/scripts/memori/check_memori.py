"""
Quick test script to check memori entities in database.
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    from app.db.session import get_db_context
    from sqlalchemy import text
    
    async with get_db_context() as db:
        # Check entities
        result = await db.execute(text("SELECT id, external_id FROM memori_entities LIMIT 10"))
        entities = result.fetchall()
        print("\n=== Memori Entities ===")
        for e in entities:
            print(f"  ID: {e[0]}, External ID: {e[1]}")
        
        # Check facts count
        result = await db.execute(text("SELECT COUNT(*) FROM memori_entity_facts"))
        count = result.scalar()
        print(f"\n=== Total Facts: {count} ===")
        
        # Check triples count
        result = await db.execute(text("SELECT COUNT(*) FROM memori_knowledge_graph"))
        count = result.scalar()
        print(f"\n=== Total Triples: {count} ===")
        
        # Sample facts
        result = await db.execute(text("SELECT id, entity_id, content FROM memori_entity_facts LIMIT 5"))
        facts = result.fetchall()
        print("\n=== Sample Facts ===")
        for f in facts:
            print(f"  ID: {f[0]}, Entity: {f[1]}, Content: {f[2][:50]}...")

if __name__ == "__main__":
    asyncio.run(main())
