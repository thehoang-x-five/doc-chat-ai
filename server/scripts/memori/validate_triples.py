"""
Script to validate and clean existing triples.
"""
import asyncio
import logging
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.db.models import MemoriEntity, MemoriEntityFact, MemoriKnowledgeGraph
from app.services.memori.triple_validator_service import TripleValidator
from app.services.memori.models import SemanticTriple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def validate_entity_triples(entity_external_id: str):
    """Validate and clean triples for an entity."""
    async with AsyncSessionLocal() as session:
        # Get entity
        result = await session.execute(
            select(MemoriEntity).where(MemoriEntity.external_id == entity_external_id)
        )
        entity = result.scalar_one_or_none()
        
        if not entity:
            logger.error(f"Entity not found: {entity_external_id}")
            return
        
        # Get all triples
        result = await session.execute(
            select(MemoriKnowledgeGraph).where(
                MemoriKnowledgeGraph.entity_id == entity.id
            )
        )
        triples_db = result.scalars().all()
        
        if not triples_db:
            logger.info(f"No triples found for entity: {entity_external_id}")
            return
        
        logger.info(f"Found {len(triples_db)} triples for entity: {entity_external_id}")
        
        # Convert to SemanticTriple objects
        triples = [
            SemanticTriple(
                subject_name=t.subject_name,
                subject_type=t.subject_type,
                predicate=t.predicate,
                object_name=t.object_name,
                object_type=t.object_type,
            )
            for t in triples_db
        ]
        
        # Get facts for context
        result = await session.execute(
            select(MemoriEntityFact).where(MemoriEntityFact.entity_id == entity.id)
        )
        facts = result.scalars().all()
        fact_contents = [f.content for f in facts]
        
        # Validate triples
        validator = TripleValidator(session)
        validated_triples = await validator.process_triples(
            triples=triples,
            entity_name=entity_external_id,
            facts=fact_contents,
            use_llm=True,
        )
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Validation Results:")
        logger.info(f"{'='*60}")
        logger.info(f"Original: {len(triples)} triples")
        logger.info(f"Validated: {len(validated_triples)} triples")
        logger.info(f"Removed: {len(triples) - len(validated_triples)} triples")
        logger.info(f"{'='*60}\n")
        
        # Show removed triples
        if len(validated_triples) < len(triples):
            logger.info("Removed triples:")
            validated_set = {
                (t.subject_name, t.predicate, t.object_name)
                for t in validated_triples
            }
            for t in triples:
                key = (t.subject_name, t.predicate, t.object_name)
                if key not in validated_set:
                    logger.info(f"  - {t.subject_name} --[{t.predicate}]--> {t.object_name}")


async def main():
    """Main function."""
    entity_id = input("Enter entity ID (e.g., test_user): ").strip()
    
    if not entity_id:
        logger.error("Entity ID is required")
        return
    
    logger.info(f"Validating triples for entity: {entity_id}")
    await validate_entity_triples(entity_id)
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
