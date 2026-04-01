"""
Script to check facts and triples in the database.
"""
import asyncio
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import MemoriEntity, MemoriEntityFact, MemoriKnowledgeGraph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_entity_memory(entity_external_id: str):
    """Check facts and triples for an entity."""
    async with AsyncSessionLocal() as session:
        # Get entity
        result = await session.execute(
            select(MemoriEntity).where(MemoriEntity.external_id == entity_external_id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            logger.error(f"Entity not found: {entity_external_id}")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Entity: {entity_external_id} (internal_id: {entity.id})")
        logger.info(f"{'='*60}")
        
        # Get facts
        result = await session.execute(
            select(MemoriEntityFact).where(MemoriEntityFact.entity_id == entity.id)
        )
        facts = result.scalars().all()
        
        logger.info(f"\n📝 FACTS ({len(facts)} total):")
        logger.info("-" * 60)
        for i, fact in enumerate(facts, 1):
            logger.info(f"{i}. {fact.content}")
            logger.info(f"   - ID: {fact.id}")
            logger.info(f"   - Importance: {fact.importance_score}")
            logger.info(f"   - Created: {fact.created_at}")
        
        # Get triples
        result = await session.execute(
            select(MemoriKnowledgeGraph).where(MemoriKnowledgeGraph.entity_id == entity.id)
        )
        triples = result.scalars().all()
        
        logger.info(f"\n🔗 TRIPLES ({len(triples)} total):")
        logger.info("-" * 60)
        for i, triple in enumerate(triples, 1):
            logger.info(
                f"{i}. {triple.subject_name} ({triple.subject_type or 'unknown'}) "
                f"--[{triple.predicate}]--> "
                f"{triple.object_name} ({triple.object_type or 'unknown'})"
            )
            logger.info(f"   - ID: {triple.id}")
            logger.info(f"   - Created: {triple.created_at}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Summary: {len(facts)} facts, {len(triples)} triples")
        logger.info(f"{'='*60}\n")


async def list_all_entities():
    """List all entities in the database."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MemoriEntity))
        entities = result.scalars().all()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"ALL ENTITIES ({len(entities)} total):")
        logger.info(f"{'='*60}")
        
        for entity in entities:
            # Count facts
            fact_count = await session.execute(
                select(func.count(MemoriEntityFact.id)).where(
                    MemoriEntityFact.entity_id == entity.id
                )
            )
            facts = fact_count.scalar() or 0
            
            # Count triples
            triple_count = await session.execute(
                select(func.count(MemoriKnowledgeGraph.id)).where(
                    MemoriKnowledgeGraph.entity_id == entity.id
                )
            )
            triples = triple_count.scalar() or 0
            
            logger.info(f"- {entity.external_id}: {facts} facts, {triples} triples")
        
        logger.info(f"{'='*60}\n")


async def main():
    """Main function."""
    print("\n1. List all entities")
    print("2. Check specific entity")
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        await list_all_entities()
    elif choice == "2":
        entity_id = input("Enter entity ID: ").strip()
        if entity_id:
            await check_entity_memory(entity_id)
        else:
            logger.error("Entity ID is required")
    else:
        # Default to list all if invalid choice
        await list_all_entities()


if __name__ == "__main__":
    asyncio.run(main())
