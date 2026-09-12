"""Shared FastAPI dependencies: auth, roles, quota, ARQ pool."""
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.core.exceptions import AuthenticationError, PermissionError_
from app.crud import user as user_crud
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import quota_service

bearer_scheme = HTTPBearer(auto_error=False)

DbDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbDep,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
) -> User:
    if credentials is None:
        raise AuthenticationError("Missing authentication credentials.")
    payload = security.decode_token(credentials.credentials)
    if not payload or payload.get("type") != security.ACCESS:
        raise AuthenticationError("Invalid or expired access token.")
    user = await user_crud.get_by_id(db, int(payload["sub"]))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or disabled.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin:
        raise PermissionError_("Administrator privileges required.")
    return user


async def enforce_quota(db: DbDep, user: CurrentUser) -> User:
    """Consume one unit of the user's daily quota or raise 429."""
    await quota_service.consume(db, user.id)
    return user


def get_arq(request: Request) -> ArqRedis:
    return request.app.state.arq
