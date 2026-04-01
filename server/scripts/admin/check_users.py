import asyncio
from app.db.session import AsyncSessionLocal
from app.db.models import User, Workspace, WorkspaceUser
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        print("Users:")
        for u in users:
            print(f"  - {u.id}: {u.email}")
        
        result = await session.execute(select(Workspace))
        workspaces = result.scalars().all()
        print("\nWorkspaces:")
        for w in workspaces:
            print(f"  - {w.id}: {w.name}")
        
        result = await session.execute(select(WorkspaceUser))
        memberships = result.scalars().all()
        print("\nMemberships:")
        for m in memberships:
            print(f"  - User {m.user_id} -> Workspace {m.workspace_id} ({m.role})")

asyncio.run(check())
