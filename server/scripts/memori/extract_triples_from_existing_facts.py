"""
Script to extract triples from existing facts that don't have triples yet.
Run this to retroactively generate triples for facts added before the auto-extraction feature.
"""
import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.db.models import MemoriEntity, MemoriEntityFact, MemoriKnowledgeGraph
from app.services.memori import MemoriManager, MemoriConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def extract_triples_for_entity(entity_external_id: str):
    """Extract triples from all facts for a specific entity."""
    async with AsyncSessionLocal() as session:
        # Get entity
        result = await session.execute(
            select(MemoriEntity).where(MemoriEntity.external_id == entity_external_id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            logger.error(f"Entity not found: {entity_external_id}")
            return
        
        # Get all facts for this entity
        result = await session.execute(
            select(MemoriEntityFact).where(MemoriEntityFact.entity_id == entity.id)
        )
        facts = result.scalars().all()
        
        if not facts:
            logger.info(f"No facts found for entity: {entity_external_id}")
            return
        
        logger.info(f"Found {len(facts)} facts for entity: {entity_external_id}")
        
        # Extract fact contents
        fact_contents = [f.content for f in facts]
        
        # Create manager
        config = MemoriConfig(
            entity_id=entity_external_id,
            workspace_id=entity.workspace_id,
        )
        manager = MemoriManager(session, config)
        
        # Extract triples from all facts
        logger.info("Extracting triples from facts...")
        logger.info(f"Facts to extract from: {fact_contents}")
        triples = await manager._extract_triples_from_facts(fact_contents, entity_external_id)
        
        if triples:
            logger.info(f"Extracted {len(triples)} triples")
            
            # Add triples to knowledge graph
            created_ids = await manager.add_semantic_triples(
                entity_id=entity_external_id,
                triples=triples,
            )
            
            await session.commit()
            logger.info(f"Successfully added {len(created_ids)} triples to knowledge graph")
        else:
            logger.warning("No triples extracted from facts")


async def extract_all_entities():
    """Extract triples for all entities that have facts."""
    async with AsyncSessionLocal() as session:
        # Get all entities
        result = await session.execute(select(MemoriEntity))
        entities = result.scalars().all()
        
        if not entities:
            logger.info("No entities found")
            return
        
        logger.info(f"Found {len(entities)} entities")
        
        for entity in entities:
            # Count facts
            fact_result = await session.execute(
                select(MemoriEntityFact).where(MemoriEntityFact.entity_id == entity.id)
            )
            facts = fact_result.scalars().all()
            
            if not facts:
                logger.info(f"Skipping {entity.external_id}: no facts")
                continue
            
            # Count existing triples
            triple_result = await session.execute(
                select(MemoriKnowledgeGraph).where(MemoriKnowledgeGraph.entity_id == entity.id)
            )
            triples = triple_result.scalars().all()
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Entity: {entity.external_id}")
            logger.info(f"Facts: {len(facts)}, Triples: {len(triples)}")
            logger.info(f"{'='*60}")
            
            # Extract triples
            await extract_triples_for_entity(entity.external_id)


async def main():
    """Main function."""
    print("\n1. Extract triples for all entities")
    print("2. Extract triples for specific entity")
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        logger.info("Starting triple extraction for all entities...")
        await extract_all_entities()
        logger.info("Done!")
    elif choice == "2":
        entity_id = input("Enter entity ID (e.g., user_123): ").strip()
        
        if not entity_id:
            logger.error("Entity ID is required")
            return
        
        logger.info(f"Starting triple extraction for entity: {entity_id}")
        await extract_triples_for_entity(entity_id)
        logger.info("Done!")
    else:
        logger.error("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
