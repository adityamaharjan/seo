"""Administrator endpoints for managing user accounts.

Every route requires the ``admin`` role. The rules that stop an administrator
locking everyone out live in :mod:`app.services.user_service`.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbDep, require_admin
from app.models.user import User, UserRole
from app.schemas.user import (
    AdminQuotaUpdate,
    AdminUserUpdate,
    PaginatedUsers,
    SessionsRevoked,
    UserDetail,
)
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])

AdminUser = Annotated[User, Depends(require_admin)]


@router.get("/users", response_model=PaginatedUsers)
async def list_users(
    db: DbDep,
    _: AdminUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Matches username or email"),
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> PaginatedUsers:
    """Paginated user directory, newest first."""
    return await user_service.list_users(
        db,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        is_active=is_active,
    )


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(user_id: int, db: DbDep, _: AdminUser) -> UserDetail:
    return await user_service.get_user(db, user_id)


@router.patch("/users/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: int, payload: AdminUserUpdate, db: DbDep, admin: AdminUser
) -> UserDetail:
    """Change a user's role or enabled status.

    Demoting or disabling someone also revokes their sessions, so the change
    takes effect at once rather than when their access token happens to expire.
    """
    return await user_service.admin_update_user(
        db,
        actor=admin,
        user_id=user_id,
        role=payload.role,
        is_active=payload.is_active,
    )


@router.patch("/users/{user_id}/quota", response_model=UserDetail)
async def update_quota(
    user_id: int, payload: AdminQuotaUpdate, db: DbDep, _: AdminUser
) -> UserDetail:
    """Override a user's daily or monthly analysis allowance."""
    return await user_service.admin_update_quota(
        db,
        user_id=user_id,
        daily_limit=payload.daily_limit,
        monthly_limit=payload.monthly_limit,
    )


@router.post("/users/{user_id}/revoke-sessions", response_model=SessionsRevoked)
async def revoke_sessions(user_id: int, db: DbDep, _: AdminUser) -> SessionsRevoked:
    """Sign a user out of every device."""
    revoked = await user_service.admin_revoke_sessions(db, user_id=user_id)
    return SessionsRevoked(revoked=revoked)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: DbDep, admin: AdminUser) -> None:
    """Delete a user along with their reports, quota and sessions."""
    await user_service.admin_delete_user(db, actor=admin, user_id=user_id)
