"""
Memori extraction background tasks.

This module contains Celery tasks for extracting facts, preferences, and attributes
from conversations in the background (non-blocking).
"""
import asyncio
from uuid import UUID
from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    name="app.queue.tasks.memori_tasks.extract_memori_facts",
    queue="default",
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def extract_memori_facts_task(
    self,
    conversation_id: str,
    workspace_id: str,
    user_id: str,
):
    """
    Background task to extract Memori facts from conversation.
    
    This task:
    1. Gets recent messages from conversation
    2. Extracts facts, preferences, attributes using LLM
    3. Stores results to database
    
    Runs asynchronously after chat response is sent to user.
    
    Args:
        conversation_id: UUID string of conversation
        workspace_id: UUID string of workspace
        user_id: UUID string of user
    """
    from app.core.config import settings
    from app.db.models import Message, Conversation
    
    logger.info(f"Starting Memori extraction for conversation {conversation_id}")
    
    # Create sync engine and session
    db_url = settings.database_url
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    sync_engine = create_engine(db_url, echo=False)
    SyncSession = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
    
    # Run async extraction in sync context
    try:
        asyncio.run(_extract_memori_async(
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            user_id=user_id,
            db_url=db_url,
        ))
        logger.info(f"Memori extraction completed for conversation {conversation_id}")
    except Exception as exc:
        logger.error(f"Memori extraction failed for conversation {conversation_id}: {exc}")
        # Retry with exponential backoff
        raise self.retry(exc=exc)


async def _extract_memori_async(
    conversation_id: str,
    workspace_id: str,
    user_id: str,
    db_url: str,
):
    """
    Async helper function to extract Memori facts.
    
    This is called by the Celery task in an asyncio.run() context.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.db.models import Message, Conversation
    from app.services.memori import MemoriManager, MemoriConfig
    # Removed AugmentationPipeline and FactExtractor imports -> using MemoriManager directly
    
    # Convert to async URL
    if "postgresql://" in db_url and "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Create async engine and session
    async_engine = create_async_engine(db_url, echo=False)
    AsyncSessionLocal = async_sessionmaker(
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with AsyncSessionLocal() as session:
        try:
            # Get conversation messages
            query = (
                select(Message)
                .where(Message.conversation_id == UUID(conversation_id))
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            result = await session.execute(query)
            messages = list(reversed(result.scalars().all()))
            
            if len(messages) < 2:
                logger.debug(f"Not enough messages ({len(messages)}) for extraction")
                return
            
            # Only extract every 2 messages (for faster learning)
            if len(messages) % 2 != 0:
                logger.debug(f"Skipping extraction - message count {len(messages)} not even")
                return
            
            # Build message list for extraction (last 6 messages max)
            recent_messages = [
                {"role": m.role, "content": m.content}
                for m in messages[-6:]
            ]
            
            logger.debug(f"Extracting from {len(recent_messages)} messages")
            
            # Setup Memori manager
            memori_config = MemoriConfig.from_conversation(
                conversation_id=UUID(conversation_id),
                workspace_id=UUID(workspace_id),
                user_id=UUID(user_id),
            )
            memori_manager = MemoriManager(session, memori_config)
            
            # Use MemoriManager to extract facts (Better Prompt & JSON output)
            # This replaces AugmentationPipeline which used a weaker prompt
            memories = await memori_manager.extract_facts_from_messages(
                messages=recent_messages,
                entity_id=user_id,
                conversation_id=UUID(conversation_id),
            )
            
            # Access extracted data
            facts_count = len(memories.entity.facts) if memories.entity.facts else 0
            triples_count = len(memories.entity.semantic_triples) if memories.entity.semantic_triples else 0
            
            logger.info(
                f"Extracted {facts_count} facts and {triples_count} triples "
                f"for conversation {conversation_id}"
            )
            
            # Note: extract_facts_from_messages ALREADY saves facts and triples to DB
            # We don't need to manually call add_facts here.
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Extraction error: {e}")
            await session.rollback()
            raise
        finally:
            await async_engine.dispose()


def _determine_preference_category(key: str) -> str:
    """Determine preference category from key."""
    if key.startswith('ui_'):
        return 'ui'
    elif key == 'language':
        return 'language'
    elif key.startswith('response_'):
        return 'response'
    return 'general'


def _determine_attribute_category(key: str) -> str:
    """Determine attribute category from key."""
    if key in ['role', 'job_title', 'position']:
        return 'role'
    elif key in ['skill', 'expertise', 'programming_language']:
        return 'skill'
    elif key in ['location', 'city', 'country']:
        return 'location'
    return 'general'
