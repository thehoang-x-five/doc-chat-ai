"""
Shared fixtures for integration tests.
Uses REAL DB (PostgreSQL) and REAL Redis — no mocks.
"""
import sys
import os
import asyncio
import pytest
from uuid import uuid4

# Ensure server is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.session import AsyncSessionLocal
from app.core.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_session():
    """Real async DB session — auto-rollback after each test."""
    async with AsyncSessionLocal() as session:
        yield session
        # Rollback any uncommitted changes
        try:
            await session.rollback()
        except Exception:
            pass


@pytest.fixture
async def redis_client():
    """Real Redis client."""
    from app.services.infrastructure.redis_manager import get_redis
    client = await get_redis()
    yield client


@pytest.fixture
async def workspace_id(db_session):
    """Get or create a test workspace, return its UUID."""
    from sqlalchemy import text
    result = await db_session.execute(
        text("SELECT id FROM workspaces LIMIT 1")
    )
    row = result.fetchone()
    if row:
        return row[0]
    # Fallback
    return uuid4()


@pytest.fixture
async def user_id(db_session):
    """Get first user for testing."""
    from sqlalchemy import text
    result = await db_session.execute(
        text("SELECT id FROM users LIMIT 1")
    )
    row = result.fetchone()
    if row:
        return row[0]
    return uuid4()


@pytest.fixture
async def conversation_id(db_session, workspace_id, user_id):
    """Create a real test conversation, return its ID."""
    from app.services.conversation.conversation_service import ConversationService
    svc = ConversationService(db_session)
    conv = await svc.create_conversation(
        workspace_id=workspace_id,
        user_id=user_id,
        title="Test Conversation (auto-created)",
    )
    return conv.id


@pytest.fixture
async def conversation_with_messages(db_session, conversation_id):
    """Conversation with a few test messages for history testing."""
    from app.services.conversation.conversation_service import ConversationService
    svc = ConversationService(db_session)
    await svc.add_user_message(conversation_id, "Xin chào, tôi là Hoàng")
    await svc.add_assistant_message(
        conversation_id=conversation_id,
        content="Chào Hoàng! Tôi có thể giúp gì cho bạn?",
        provider="test",
        model="test-model",
    )
    await svc.add_user_message(conversation_id, "Giúp tôi tìm tài liệu về AI")
    return conversation_id
