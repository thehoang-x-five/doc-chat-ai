"""Quick debug script for chat flow."""
import asyncio
import sys
sys.path.insert(0, '.')

async def main():
    print("Starting debug...")
    
    # Test 1: Database connection
    print("\n[1] Testing database connection...")
    try:
        from app.db.session import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            row = result.fetchone()
            print(f"  Database OK: {row}")
    except Exception as e:
        print(f"  Database ERROR: {e}")
        return
    
    # Test 2: Get workspace
    print("\n[2] Getting workspace...")
    try:
        from app.db.models import Workspace
        from sqlalchemy import select
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Workspace).limit(1))
            workspace = result.scalar_one_or_none()
            if workspace:
                print(f"  Workspace: {workspace.id} - {workspace.name}")
                workspace_id = workspace.id
            else:
                print("  No workspace found!")
                return
    except Exception as e:
        print(f"  Workspace ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 3: Stateless query
    print("\n[3] Testing stateless query...")
    try:
        from app.services.chat_service import ChatService
        
        async with AsyncSessionLocal() as session:
            chat_service = ChatService(session)
            
            response = await chat_service.stateless_query(
                workspace_id=workspace_id,
                question="Xin chào",
            )
            print(f"  Answer: {response.answer[:100]}...")
            print(f"  Provider: {response.provider}")
            print(f"  Citations: {len(response.citations)}")
    except Exception as e:
        print(f"  Stateless query ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Conversation chat (the problematic one)
    print("\n[4] Testing conversation chat...")
    try:
        from app.db.models import User
        
        async with AsyncSessionLocal() as session:
            # Get user
            result = await session.execute(select(User).limit(1))
            user = result.scalar_one_or_none()
            
            if not user:
                print("  No user found!")
                return
            
            print(f"  User: {user.id}")
            
            chat_service = ChatService(session)
            
            # Create conversation
            print("  Creating conversation...")
            conversation = await chat_service.create_conversation(
                workspace_id=workspace_id,
                user_id=user.id,
                title="Debug Test",
            )
            print(f"  Conversation: {conversation.id}")
            
            # Send message
            print("  Sending message...")
            user_msg, assistant_msg = await chat_service.send_message(
                conversation_id=conversation.id,
                content="Xin chào",
            )
            
            print(f"  User msg ID: {user_msg.id}")
            print(f"  Assistant msg ID: {assistant_msg.id}")
            print(f"  Answer: {assistant_msg.content[:100]}...")
            print("  SUCCESS!")
            
    except Exception as e:
        print(f"  Conversation chat ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n[Done]")

if __name__ == "__main__":
    asyncio.run(main())
