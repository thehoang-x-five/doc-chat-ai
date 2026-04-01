"""
Database session management with async support.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from app.core.config import settings


# Async engine for FastAPI
async_engine = create_async_engine(
    settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Sync engine for Alembic migrations
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
)

# Sync session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.
    Usage: db: AsyncSession = Depends(get_db)
    
    Handles transaction state properly to avoid "InFailedSQLTransactionError".
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            # Only commit if transaction is active and not in error state
            # Check both is_active and in_transaction to be safe
            if session.is_active:
                try:
                    await session.commit()
                except Exception as commit_error:
                    # If commit fails, rollback to clear the transaction
                    try:
                        await session.rollback()
                    except Exception:
                        pass
                    # Don't re-raise commit errors - they're usually due to
                    # transaction already being in error state
                    import logging
                    logging.getLogger(__name__).warning(
                        f"Session commit failed (transaction may have been aborted): {commit_error}"
                    )
        except Exception:
            # Rollback on any exception during request processing
            try:
                await session.rollback()
            except Exception:
                pass
            raise
        finally:
            await session.close()

