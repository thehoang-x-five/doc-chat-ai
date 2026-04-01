"""
Workspace service cho việc quản lý workspace và cộng tác.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Workspace, WorkspaceUser, User, WorkspaceRole


class WorkspaceServiceError(Exception):
    """Base exception cho workspace service errors."""
    pass


class WorkspaceNotFoundError(WorkspaceServiceError):
    """Không tìm thấy Workspace."""
    pass


class PermissionDeniedError(WorkspaceServiceError):
    """Người dùng không có quyền."""
    pass


class MemberExistsError(WorkspaceServiceError):
    """Thành viên đã tồn tại trong workspace."""
    pass


class WorkspaceService:
    """
    Workspace service xử lý workspace CRUD và quản lý thành viên.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    # =========================================================================
    # WORKSPACE CRUD
    # =========================================================================
    
    async def create(
        self,
        user_id: UUID,
        name: str,
        plan: str = "free",
        answer_policy: str = "balanced",
        evidence_threshold: float = 0.7,
    ) -> Workspace:
        """
        Tạo workspace mới và gán người tạo làm OWNER.
        
        Args:
            user_id: ID người tạo
            name: Tên Workspace
            plan: Gói đăng ký (subscription plan)
            answer_policy: Chính sách trả lời RAG (strict/balanced/open)
            evidence_threshold: Ngưỡng điểm evidence
            
        Returns:
            Workspace đã tạo
        """
        # Create workspace
        workspace = Workspace(
            name=name,
            owner_id=user_id,
            plan=plan,
            answer_policy=answer_policy,
            evidence_threshold=evidence_threshold,
        )
        self.session.add(workspace)
        await self.session.flush()
        
        # Thêm người tạo làm OWNER member
        workspace_user = WorkspaceUser(
            workspace_id=workspace.id,
            user_id=user_id,
            role=WorkspaceRole.OWNER,
        )
        self.session.add(workspace_user)
        await self.session.flush()
        await self.session.refresh(workspace)
        
        return workspace
    
    async def get(self, workspace_id: UUID, user_id: UUID) -> Workspace:
        """
        Lấy workspace theo ID nếu user là thành viên.
        
        Args:
            workspace_id: ID Workspace
            user_id: ID người dùng yêu cầu
            
        Returns:
            Workspace nếu tìm thấy và user là thành viên
            
        Raises:
            WorkspaceNotFoundError: Nếu không tìm thấy workspace
            PermissionDeniedError: Nếu user không phải là thành viên
        """
        # Kiểm tra thành viên
        membership = await self._get_membership(workspace_id, user_id)
        if not membership:
            raise PermissionDeniedError("Không phải là thành viên của workspace này")
        
        result = await self.session.execute(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(selectinload(Workspace.members))
        )
        workspace = result.scalar_one_or_none()
        
        if not workspace:
            raise WorkspaceNotFoundError("Không tìm thấy Workspace")
        
        return workspace
    
    async def list_for_user(self, user_id: UUID) -> List[Workspace]:
        """
        Liệt kê tất cả workspaces mà user là thành viên.
        
        Args:
            user_id: ID người dùng
            
        Returns:
            Danh sách workspaces
        """
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceUser)
            .where(WorkspaceUser.user_id == user_id)
            .options(selectinload(Workspace.members))
        )
        return list(result.scalars().all())
    
    async def update(
        self,
        workspace_id: UUID,
        user_id: UUID,
        name: Optional[str] = None,
        answer_policy: Optional[str] = None,
        evidence_threshold: Optional[float] = None,
    ) -> Workspace:
        """
        Cập nhật setting workspace. Chỉ OWNER mới có quyền cập nhật.
        """
        # Kiểm tra quyền
        if not await self._check_permission(workspace_id, user_id, "update"):
            raise PermissionDeniedError("Chỉ owner mới có thể cập nhật workspace")
        
        updates = {}
        if name is not None:
            updates["name"] = name
        if answer_policy is not None:
            updates["answer_policy"] = answer_policy
        if evidence_threshold is not None:
            updates["evidence_threshold"] = evidence_threshold
        
        if updates:
            await self.session.execute(
                update(Workspace)
                .where(Workspace.id == workspace_id)
                .values(**updates)
            )
            await self.session.flush()
        
        return await self.get(workspace_id, user_id)

    async def delete(self, workspace_id: UUID, user_id: UUID) -> bool:
        """
        Xóa workspace. Chỉ OWNER mới có quyền xóa.
        Cascade tới tất cả documents, jobs, conversations.
        """
        if not await self._check_permission(workspace_id, user_id, "delete"):
            raise PermissionDeniedError("Chỉ owner mới có thể xóa workspace")
        
        result = await self.session.execute(
            delete(Workspace).where(Workspace.id == workspace_id)
        )
        await self.session.flush()
        return result.rowcount > 0
    
    # =========================================================================
    # QUẢN LÝ THÀNH VIÊN (MEMBER MANAGEMENT)
    # =========================================================================
    
    async def add_member(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        member_email: str,
        role: str = WorkspaceRole.VIEWER,
    ) -> WorkspaceUser:
        """
        Thêm thành viên vào workspace. Chỉ OWNER mới có quyền thêm.
        
        Args:
            workspace_id: ID Workspace
            owner_id: User ID của Owner (phải là owner)
            member_email: Email của user cần thêm
            role: Vai trò gán cho user (EDITOR hoặc VIEWER)
        """
        # Kiểm tra quyền
        if not await self._check_permission(workspace_id, owner_id, "manage_members"):
            raise PermissionDeniedError("Chỉ owner mới có thể thêm thành viên")
        
        # Tìm user theo email
        result = await self.session.execute(
            select(User).where(User.email == member_email)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise WorkspaceServiceError(f"Không tìm thấy user với email {member_email}")
        
        # Kiểm tra nếu đã là thành viên
        existing = await self._get_membership(workspace_id, user.id)
        if existing:
            raise MemberExistsError("User đã là thành viên rồi")
        
        # Validate role (không thể thêm làm OWNER)
        if role == WorkspaceRole.OWNER:
            role = WorkspaceRole.EDITOR
        
        # Thêm thành viên
        workspace_user = WorkspaceUser(
            workspace_id=workspace_id,
            user_id=user.id,
            role=role,
        )
        self.session.add(workspace_user)
        await self.session.flush()
        await self.session.refresh(workspace_user)
        
        return workspace_user
    
    async def remove_member(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        member_id: UUID,
    ) -> bool:
        """
        Xóa thành viên khỏi workspace. Chỉ OWNER mới có quyền xóa.
        Owner không thể xóa chính mình.
        """
        if not await self._check_permission(workspace_id, owner_id, "manage_members"):
            raise PermissionDeniedError("Chỉ owner mới có thể xóa thành viên")
        
        # Không thể xóa owner
        workspace = await self.session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        ws = workspace.scalar_one_or_none()
        if ws and ws.owner_id == member_id:
            raise PermissionDeniedError("Không thể xóa owner của workspace")
        
        result = await self.session.execute(
            delete(WorkspaceUser)
            .where(WorkspaceUser.workspace_id == workspace_id)
            .where(WorkspaceUser.user_id == member_id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def update_member_role(
        self,
        workspace_id: UUID,
        owner_id: UUID,
        member_id: UUID,
        new_role: str,
    ) -> WorkspaceUser:
        """
        Cập nhật vai trò thành viên. Chỉ OWNER mới có quyền cập nhật.
        """
        if not await self._check_permission(workspace_id, owner_id, "manage_members"):
            raise PermissionDeniedError("Chỉ owner mới có thể cập nhật vai trò thành viên")
        
        # Không thể thay đổi role của owner
        workspace = await self.session.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        ws = workspace.scalar_one_or_none()
        if ws and ws.owner_id == member_id:
            raise PermissionDeniedError("Không thể thay đổi vai trò của owner")
        
        # Valiadte role
        if new_role not in [WorkspaceRole.EDITOR, WorkspaceRole.VIEWER]:
            raise WorkspaceServiceError("Role không hợp lệ")
        
        await self.session.execute(
            update(WorkspaceUser)
            .where(WorkspaceUser.workspace_id == workspace_id)
            .where(WorkspaceUser.user_id == member_id)
            .values(role=new_role)
        )
        await self.session.flush()
        
        result = await self.session.execute(
            select(WorkspaceUser)
            .where(WorkspaceUser.workspace_id == workspace_id)
            .where(WorkspaceUser.user_id == member_id)
        )
        return result.scalar_one()
    
    async def get_members(self, workspace_id: UUID, user_id: UUID) -> List[WorkspaceUser]:
        """Lấy tất cả thành viên của workspace."""
        # Kiểm tra thành viên
        if not await self._get_membership(workspace_id, user_id):
            raise PermissionDeniedError("Không phải là thành viên của workspace này")
        
        result = await self.session.execute(
            select(WorkspaceUser)
            .where(WorkspaceUser.workspace_id == workspace_id)
            .options(selectinload(WorkspaceUser.user))
        )
        return list(result.scalars().all())
    
    # =========================================================================
    # KIỂM TRA QUYỀN (PERMISSION CHECKING)
    # =========================================================================
    
    async def _get_membership(
        self, workspace_id: UUID, user_id: UUID
    ) -> Optional[WorkspaceUser]:
        """Lấy thông tin thành viên của user trong workspace."""
        result = await self.session.execute(
            select(WorkspaceUser)
            .where(WorkspaceUser.workspace_id == workspace_id)
            .where(WorkspaceUser.user_id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _check_permission(
        self, workspace_id: UUID, user_id: UUID, action: str
    ) -> bool:
        """
        Kiểm tra xem người dùng có quyền thực hiện hành động không.
        
        Actions:
        - read: VIEWER, EDITOR, OWNER
        - write: EDITOR, OWNER
        - update: OWNER only
        - delete: OWNER only
        - manage_members: OWNER only
        """
        membership = await self._get_membership(workspace_id, user_id)
        if not membership:
            return False
        
        role = membership.role
        
        if action == "read":
            return role in [WorkspaceRole.VIEWER, WorkspaceRole.EDITOR, WorkspaceRole.OWNER]
        elif action == "write":
            return role in [WorkspaceRole.EDITOR, WorkspaceRole.OWNER]
        elif action in ["update", "delete", "manage_members"]:
            return role == WorkspaceRole.OWNER
        
        return False
    
    async def check_permission(
        self, workspace_id: UUID, user_id: UUID, action: str
    ) -> bool:
        """Public method để kiểm tra quyền."""
        return await self._check_permission(workspace_id, user_id, action)
