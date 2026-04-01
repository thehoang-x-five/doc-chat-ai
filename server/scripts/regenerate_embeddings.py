"""
Script to regenerate embeddings for existing chunks.

This script will:
1. Find all chunks without embeddings
2. Generate embeddings using EmbeddingService
3. Update chunks with new embeddings
4. Show progress and statistics
"""
import asyncio
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func, update
from app.db.session import AsyncSessionLocal
from app.db.models import Chunk, Document, DocumentVersion
from app.services.embedding_service import get_embedding_service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def regenerate_embeddings():
    """Regenerate embeddings for all chunks."""
    
    logger.info("🚀 Starting embedding regeneration...")
    
    async with AsyncSessionLocal() as session:
        # Count total chunks
        result = await session.execute(
            select(func.count(Chunk.id))
        )
        total_chunks = result.scalar()
        logger.info(f"📦 Total chunks: {total_chunks}")
        
        # Count chunks without embeddings
        try:
            result = await session.execute(
                select(func.count(Chunk.id)).where(Chunk.embedding.is_(None))
            )
            chunks_without_embeddings = result.scalar()
            logger.info(f"❌ Chunks without embeddings: {chunks_without_embeddings}")
        except AttributeError:
            logger.error("⚠️  Chunk.embedding attribute not available. Is pgvector installed?")
            return
        
        if chunks_without_embeddings == 0:
            logger.info("✅ All chunks already have embeddings!")
            return
        
        # Get embedding service (singleton - model loaded once)
        embedding_service = get_embedding_service()
        logger.info(f"🤖 Using embedding model: {embedding_service.model_name}")
        
        # Process chunks in batches
        batch_size = 32  # Process 32 chunks at a time
        offset = 0
        processed = 0
        
        while True:
            # Fetch batch of chunks without embeddings
            result = await session.execute(
                select(Chunk)
                .where(Chunk.embedding.is_(None))
                .limit(batch_size)
                .offset(offset)
            )
            chunks = result.scalars().all()
            
            if not chunks:
                break
            
            logger.info(f"📝 Processing batch {offset // batch_size + 1} ({len(chunks)} chunks)...")
            
            # Generate embeddings for batch
            chunk_texts = [chunk.content for chunk in chunks if chunk.content]
            
            if not chunk_texts:
                logger.warning(f"⚠️  Skipping batch - no content")
                offset += batch_size
                continue
            
            try:
                # Generate embeddings (returns tuple: embeddings, model_info)
                embeddings, model_info = embedding_service.embed_batch(chunk_texts)
                logger.info(f"✅ Generated {len(embeddings)} embeddings")
                
                # Update chunks with embeddings
                for chunk, embedding in zip(chunks, embeddings):
                    if chunk.content:  # Only update chunks with content
                        chunk.embedding = embedding
                        processed += 1
                
                # Commit batch
                await session.commit()
                logger.info(f"💾 Saved batch ({processed}/{chunks_without_embeddings} total)")
                
            except Exception as e:
                logger.error(f"❌ Error processing batch: {e}")
                await session.rollback()
            
            offset += batch_size
        
        logger.info(f"\n✅ Embedding regeneration complete!")
        logger.info(f"📊 Statistics:")
        logger.info(f"   - Total chunks: {total_chunks}")
        logger.info(f"   - Processed: {processed}")
        logger.info(f"   - Remaining: {chunks_without_embeddings - processed}")


async def show_stats():
    """Show embedding statistics."""
    async with AsyncSessionLocal() as session:
        # Count total chunks
        result = await session.execute(
            select(func.count(Chunk.id))
        )
        total_chunks = result.scalar()
        
        # Count chunks with embeddings
        try:
            result = await session.execute(
                select(func.count(Chunk.id)).where(Chunk.embedding.isnot(None))
            )
            chunks_with_embeddings = result.scalar()
            
            # Count chunks without embeddings
            result = await session.execute(
                select(func.count(Chunk.id)).where(Chunk.embedding.is_(None))
            )
            chunks_without_embeddings = result.scalar()
            
            logger.info(f"\n📊 Embedding Statistics:")
            logger.info(f"   - Total chunks: {total_chunks}")
            logger.info(f"   - With embeddings: {chunks_with_embeddings} ({chunks_with_embeddings / total_chunks * 100:.1f}%)")
            logger.info(f"   - Without embeddings: {chunks_without_embeddings} ({chunks_without_embeddings / total_chunks * 100:.1f}%)")
            
        except AttributeError:
            logger.error("⚠️  Chunk.embedding attribute not available. Is pgvector installed?")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Regenerate embeddings for chunks")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    args = parser.parse_args()
    
    if args.stats:
        asyncio.run(show_stats())
    else:
        asyncio.run(regenerate_embeddings())
