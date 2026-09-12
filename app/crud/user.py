"""Data-access functions for users."""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole


async def get_by_id(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()


async def get_by_username(db: AsyncSession, username: str) -> User | None:
    res = await db.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()


async def get_existing(db: AsyncSession, email: str, username: str) -> User | None:
    res = await db.execute(
        select(User).where(or_(User.email == email, User.username == username))
    )
    return res.scalars().first()


async def create(
    db: AsyncSession, *, username: str, email: str, hashed_password: str
) -> User:
    user = User(username=username, email=email, hashed_password=hashed_password)
    db.add(user)
    await db.flush()
    return user


def _search_filter(stmt: Select, search: str | None) -> Select:
    if not search:
        return stmt
    pattern = f"%{search.strip()}%"
    return stmt.where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))


async def list_users(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    """Paginated user directory for administrators, newest first."""
    filters = []
    if role is not None:
        filters.append(User.role == role)
    if is_active is not None:
        filters.append(User.is_active.is_(is_active))

    count_stmt = _search_filter(select(func.count()).select_from(User), search)
    for condition in filters:
        count_stmt = count_stmt.where(condition)
    total = await db.scalar(count_stmt)

    stmt = _search_filter(
        select(User).options(selectinload(User.quota)), search
    )
    for condition in filters:
        stmt = stmt.where(condition)
    stmt = (
        stmt.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all()), int(total or 0)


async def get_with_quota(db: AsyncSession, user_id: int) -> User | None:
    res = await db.execute(
        select(User).options(selectinload(User.quota)).where(User.id == user_id)
    )
    return res.scalar_one_or_none()


async def count_active_admins(db: AsyncSession, *, excluding: int | None = None) -> int:
    """How many enabled administrators remain, optionally ignoring one id.

    Used to refuse the change that would leave nobody able to administer.
    """
    stmt = select(func.count()).select_from(User).where(
        User.role == UserRole.admin, User.is_active.is_(True)
    )
    if excluding is not None:
        stmt = stmt.where(User.id != excluding)
    return int(await db.scalar(stmt) or 0)


async def delete(db: AsyncSession, user: User) -> None:
    await db.delete(user)
    await db.flush()
