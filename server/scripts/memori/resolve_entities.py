"""
Script to resolve and merge entity aliases.
"""
import asyncio
import logging
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import MemoriEntity
from app.services.memori.entity_resolver_service import EntityResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def resolve_entity(entity_external_id: str, canonical_name: str = None):
    """Resolve and merge entity aliases."""
    async with AsyncSessionLocal() as session:
        resolver = EntityResolver(session)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Resolving entity: {entity_external_id}")
        if canonical_name:
            logger.info(f"Canonical name: {canonical_name}")
        else:
            logger.info("Auto-detecting canonical name...")
        logger.info(f"{'='*60}\n")
        
        result = await resolver.resolve_and_merge(
            entity_external_id=entity_external_id,
            canonical_name=canonical_name,
        )
        
        if "error" in result:
            logger.error(f"Error: {result['error']}")
            return
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Resolution Complete!")
        logger.info(f"{'='*60}")
        logger.info(f"Canonical Name: {result['canonical_name']}")
        logger.info(f"Aliases Found: {', '.join(result['aliases_found']) if result['aliases_found'] else 'None'}")
        logger.info(f"Triples Updated: {result['triples_updated']}")
        logger.info(f"{'='*60}\n")


async def list_entities():
    """List all entities."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(MemoriEntity))
        entities = result.scalars().all()
        
        logger.info(f"\n{'='*60}")
        logger.info(f"ALL ENTITIES ({len(entities)} total):")
        logger.info(f"{'='*60}")
        
        for i, entity in enumerate(entities, 1):
            logger.info(f"{i}. {entity.external_id}")
        
        logger.info(f"{'='*60}\n")


async def main():
    """Main function."""
    print("\n1. Resolve specific entity")
    print("2. List all entities")
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == "1":
        entity_id = input("Enter entity ID (e.g., test_user): ").strip()
        if not entity_id:
            logger.error("Entity ID is required")
            return
        
        canonical_name = input("Enter canonical name (or press Enter to auto-detect): ").strip()
        canonical_name = canonical_name if canonical_name else None
        
        await resolve_entity(entity_id, canonical_name)
    elif choice == "2":
        await list_entities()
    else:
        logger.error("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())
