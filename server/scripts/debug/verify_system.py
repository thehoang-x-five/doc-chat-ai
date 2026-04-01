"""
Comprehensive system verification script.
Tests all components: database, user, workspace, conversation, memory, RAG.
"""
import asyncio
import logging
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_all():
    """Run all tests."""
    from app.db.session import AsyncSessionLocal
    from app.db.models import User, Workspace, WorkspaceUser, Conversation, Message, Document, DocumentCategory
    from app.core.security import hash_password
    from sqlalchemy import select
    
    print("=" * 60)
    print("COMPREHENSIVE SYSTEM VERIFICATION")
    print("=" * 60)
    
    async with AsyncSessionLocal() as session:
        # ============================================================
        # 1. Get or Create test user
        # ============================================================
        print("\n[1] Getting or creating test user...")
        result = await session.execute(
            select(User).where(User.email == "test@example.com")
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                id=uuid4(),
                email="test@example.com",
                password_hash=hash_password("test123"),
                full_name="Test User",
                role_global="user",
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"    ✓ User created: {user.id}")
        else:
            print(f"    ✓ User exists: {user.id}")
        
        # ============================================================
        # 2. Get or Create workspace
        # ============================================================
        print("\n[2] Getting or creating workspace...")
        result = await session.execute(
            select(Workspace).where(Workspace.owner_id == user.id)
        )
        workspace = result.scalar_one_or_none()
        
        if not workspace:
            workspace = Workspace(
                id=uuid4(),
                name="Test Workspace",
                owner_id=user.id,
                plan="free",
                answer_policy="balanced",
                evidence_threshold=0.5,
            )
            session.add(workspace)
            await session.commit()
            await session.refresh(workspace)
            print(f"    ✓ Workspace created: {workspace.id}")
            
            # Add user to workspace
            workspace_user = WorkspaceUser(
                workspace_id=workspace.id,
                user_id=user.id,
                role="owner",
            )
            session.add(workspace_user)
            await session.commit()
            print(f"    ✓ User added to workspace")
        else:
            print(f"    ✓ Workspace exists: {workspace.id}")
        
        # ============================================================
        # 3. Test DocumentCategory (new table)
        # ============================================================
        print("\n[3] Testing DocumentCategory table...")
        try:
            result = await session.execute(
                select(DocumentCategory).where(
                    DocumentCategory.workspace_id == workspace.id,
                    DocumentCategory.slug == "test-category"
                )
            )
            category = result.scalar_one_or_none()
            
            if not category:
                category = DocumentCategory(
                    id=uuid4(),
                    workspace_id=workspace.id,
                    name="Test Category",
                    slug="test-category",
                    description="Test category for verification",
                )
                session.add(category)
                await session.commit()
                await session.refresh(category)
                print(f"    ✓ DocumentCategory created: {category.id}")
            else:
                print(f"    ✓ DocumentCategory exists: {category.id}")
        except Exception as e:
            print(f"    ✗ DocumentCategory failed: {e}")
            await session.rollback()
        
        # ============================================================
        # 4. Create conversation
        # ============================================================
        print("\n[4] Creating conversation...")
        conversation = Conversation(
            id=uuid4(),
            workspace_id=workspace.id,
            title="Test Conversation",
            created_by=user.id,
        )
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        print(f"    ✓ Conversation created: {conversation.id}")
        
        # ============================================================
        # 5. Test ChatService
        # ============================================================
        print("\n[5] Testing ChatService...")
        try:
            from app.services.chat_service import ChatService
            chat_service = ChatService(session)
            
            # Add user message
            user_msg = await chat_service.add_user_message(
                conversation.id, "Xin chào, đây là tin nhắn test"
            )
            print(f"    ✓ User message added: {user_msg.id}")
        except Exception as e:
            print(f"    ✗ ChatService failed: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        
        # ============================================================
        # 6. Test MemoryManager
        # ============================================================
        print("\n[6] Testing MemoryManager...")
        try:
            from app.services.memory_manager import MemoryManager
            memory_manager = MemoryManager(session)
            
            # Get memory
            memory = await memory_manager.get_memory(conversation.id)
            print(f"    ✓ Memory retrieved: {len(memory.short_term)} short-term entries")
            
            # Check if should summarize
            should_summarize = await memory_manager.should_summarize(conversation.id)
            print(f"    ✓ Should summarize: {should_summarize}")
            
        except Exception as e:
            print(f"    ✗ MemoryManager failed: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        
        # ============================================================
        # 7. Test ConversationSummary
        # ============================================================
        print("\n[7] Testing ConversationSummary...")
        try:
            from app.db.models import ConversationSummary
            
            summary = ConversationSummary(
                id=uuid4(),
                conversation_id=conversation.id,
                summary_text="This is a test summary",
                messages_summarized=1,
            )
            session.add(summary)
            await session.commit()
            await session.refresh(summary)
            print(f"    ✓ ConversationSummary created: {summary.id}")
        except Exception as e:
            print(f"    ✗ ConversationSummary failed: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        
        # ============================================================
        # 8. Test CategoryService
        # ============================================================
        print("\n[8] Testing CategoryService...")
        try:
            from app.services.category_service import CategoryService
            category_service = CategoryService(session)
            
            # Get category names
            names = await category_service.get_category_names(workspace.id)
            print(f"    ✓ Category names: {names}")
            
        except Exception as e:
            print(f"    ✗ CategoryService failed: {e}")
            import traceback
            traceback.print_exc()
            await session.rollback()
        
        # ============================================================
        # 9. Verify session is still healthy after all operations
        # ============================================================
        print("\n[9] Verifying session health...")
        try:
            # Try a simple query
            result = await session.execute(select(User).limit(1))
            user_check = result.scalar_one_or_none()
            print(f"    ✓ Session is healthy, user query works")
        except Exception as e:
            print(f"    ✗ Session health check failed: {e}")
            await session.rollback()
        
        # ============================================================
        # Summary
        # ============================================================
        print("\n" + "=" * 60)
        print("VERIFICATION COMPLETE")
        print("=" * 60)
        print(f"\nTest User: test@example.com / test123")
        print(f"Workspace ID: {workspace.id}")
        print(f"Conversation ID: {conversation.id}")


if __name__ == "__main__":
    asyncio.run(test_all())
