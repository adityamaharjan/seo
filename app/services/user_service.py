"""User management: self-service profile edits and administrator actions.

The guard rails here exist so that no single request can leave the system
without an administrator, and so that changing someone's access takes effect
immediately rather than whenever their current tokens happen to expire.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionError_,
)
from app.crud import quota as quota_crud
from app.crud import refresh_token as token_crud
from app.crud import report as report_crud
from app.crud import user as user_crud
from app.models.quota import Quota
from app.models.user import User, UserRole
from app.schemas.user import PaginatedUsers, UserDetail, UserQuotaSummary

# --- assembling responses -------------------------------------------------

def _quota_summary(quota: Quota | None) -> UserQuotaSummary | None:
    if quota is None:
        return None
    return UserQuotaSummary(
        daily_limit=quota.daily_limit,
        used_today=quota.used_today,
        monthly_limit=quota.monthly_limit,
        used_this_month=quota.used_this_month,
        day_reset_date=quota.day_reset_date,
    )


def _detail(user: User, report_count: int) -> UserDetail:
    return UserDetail(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
        report_count=report_count,
        quota=_quota_summary(user.quota),
    )


# --- self service ---------------------------------------------------------

async def update_profile(
    db: AsyncSession, user: User, *, username: str | None, email: str | None
) -> User:
    """Change your own username or email, refusing values already in use."""
    if username is not None and username != user.username:
        existing = await user_crud.get_by_username(db, username)
        if existing and existing.id != user.id:
            raise ConflictError("That username is already taken.")
        user.username = username

    if email is not None and email != user.email:
        existing = await user_crud.get_by_email(db, email)
        if existing and existing.id != user.id:
            raise ConflictError("That email is already registered.")
        user.email = email

    await db.commit()
    await db.refresh(user)
    return user


async def change_password(
    db: AsyncSession, user: User, *, current_password: str, new_password: str
) -> int:
    """Replace a password and sign every session out. Returns sessions ended.

    Revoking outstanding refresh tokens is the point of the exercise: a
    password change is usually a response to it being exposed, so a stolen
    token must not keep working afterwards.
    """
    if not security.verify_password(current_password, user.hashed_password):
        raise AuthenticationError("Your current password is not correct.")

    user.hashed_password = security.hash_password(new_password)
    revoked = await token_crud.revoke_all_for_user(db, user.id)
    await db.commit()
    return revoked


# --- administration -------------------------------------------------------

async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> PaginatedUsers:
    users, total = await user_crud.list_users(
        db,
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        is_active=is_active,
    )
    counts = await report_crud.count_for_users(db, [u.id for u in users])
    return PaginatedUsers(
        items=[_detail(u, counts.get(u.id, 0)) for u in users],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_user(db: AsyncSession, user_id: int) -> UserDetail:
    user = await user_crud.get_with_quota(db, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return _detail(user, await report_crud.count_for_user(db, user_id))


async def _require_target(db: AsyncSession, user_id: int) -> User:
    user = await user_crud.get_with_quota(db, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


async def admin_update_user(
    db: AsyncSession,
    *,
    actor: User,
    user_id: int,
    role: UserRole | None,
    is_active: bool | None,
) -> UserDetail:
    """Change a user's role or enabled status.

    Administrators may not demote or disable themselves, because a single
    mistaken click would otherwise cost them their own access, and the last
    enabled administrator may not be removed by any route.
    """
    target = await _require_target(db, user_id)

    if target.id == actor.id:
        if role is not None and role != target.role:
            raise PermissionError_("You cannot change your own role.")
        if is_active is not None and not is_active:
            raise PermissionError_("You cannot disable your own account.")

    losing_admin = (role is not None and role != UserRole.admin) or is_active is False
    if target.role == UserRole.admin and target.is_active and losing_admin:
        if await user_crud.count_active_admins(db, excluding=target.id) == 0:
            raise ConflictError(
                "This is the only enabled administrator. Promote someone else first."
            )

    if role is not None:
        target.role = role
    if is_active is not None:
        target.is_active = is_active

    # Losing admin rights or being disabled must bite immediately, not once the
    # current access token expires.
    if losing_admin:
        await token_crud.revoke_all_for_user(db, target.id)

    await db.commit()
    await db.refresh(target)
    return _detail(target, await report_crud.count_for_user(db, target.id))


async def admin_update_quota(
    db: AsyncSession, *, user_id: int, daily_limit: int | None, monthly_limit: int | None
) -> UserDetail:
    """Override a user's allowance, e.g. to lift the free tier for someone."""
    target = await _require_target(db, user_id)
    quota = target.quota or await quota_crud.create(db, target.id)

    if daily_limit is not None:
        quota.daily_limit = daily_limit
    if monthly_limit is not None:
        quota.monthly_limit = monthly_limit

    await db.commit()
    refreshed = await _require_target(db, user_id)
    return _detail(refreshed, await report_crud.count_for_user(db, user_id))


async def admin_delete_user(db: AsyncSession, *, actor: User, user_id: int) -> None:
    """Remove a user and everything of theirs, via the cascade on the model."""
    target = await _require_target(db, user_id)

    if target.id == actor.id:
        raise PermissionError_("You cannot delete your own account from here.")
    if (
        target.role == UserRole.admin
        and target.is_active
        and await user_crud.count_active_admins(db, excluding=target.id) == 0
    ):
        raise ConflictError(
            "This is the only enabled administrator. Promote someone else first."
        )

    await user_crud.delete(db, target)
    await db.commit()


async def admin_revoke_sessions(db: AsyncSession, *, user_id: int) -> int:
    """Force a user to sign in again everywhere. Returns sessions ended."""
    target = await _require_target(db, user_id)
    revoked = await token_crud.revoke_all_for_user(db, target.id)
    await db.commit()
    return revoked
