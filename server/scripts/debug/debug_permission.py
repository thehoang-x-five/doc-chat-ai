import asyncio
from uuid import UUID
from app.db.session import AsyncSessionLocal
from app.services.workspace_service import WorkspaceService

async def check():
    user_id = UUID("38582866-0057-463a-8164-ef435f3cb74d")
    workspace_id = UUID("651d9005-11db-41fd-bacd-74b6b96c7f64")
    
    async with AsyncSessionLocal() as session:
        ws = WorkspaceService(session)
        
        # Check permission
        has_perm = await ws.check_permission(workspace_id, user_id, "read")
        print(f"Has read permission: {has_perm}")
        
        # Get membership
        from app.db.models import WorkspaceUser
        from sqlalchemy import select
        
        result = await session.execute(
            select(WorkspaceUser).where(
                WorkspaceUser.workspace_id == workspace_id,
                WorkspaceUser.user_id == user_id
            )
        )
        membership = result.scalar_one_or_none()
        if membership:
            print(f"Membership found: role={membership.role}")
        else:
            print("No membership found!")

asyncio.run(check())
