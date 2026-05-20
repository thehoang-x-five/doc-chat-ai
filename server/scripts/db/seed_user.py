import asyncio
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionLocal
from app.db.models import User, Workspace, WorkspaceUser
from app.core.security import hash_password
from sqlalchemy import select

async def seed():
    async with AsyncSessionLocal() as session:
        # Check if user exists
        email = "52300065@student.tdtu.edu.vn"
        password = "Thedeptrai1@"
        
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"Creating user {email}...")
            user = User(
                id=uuid.uuid4(),
                email=email,
                password_hash=hash_password(password),
                full_name="The Hoang",
                role_global="ADMIN"
            )
            session.add(user)
            await session.flush()
            
            # Create default workspace
            print("Creating default workspace...")
            workspace = Workspace(
                id=uuid.uuid4(),
                name="My First Workspace",
                owner_id=user.id,
                plan="free"
            )
            session.add(workspace)
            await session.flush()
            
            # Add user to workspace
            print("Adding user to workspace...")
            workspace_user = WorkspaceUser(
                workspace_id=workspace.id,
                user_id=user.id,
                role="OWNER"
            )
            session.add(workspace_user)
            
            await session.commit()
            print("Successfully seeded user and workspace.")
        else:
            print(f"User {email} already exists.")

if __name__ == "__main__":
    asyncio.run(seed())
