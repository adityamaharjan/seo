"""Authentication endpoints."""
from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbDep
from app.core.ratelimit import (
    LoginIPLimit,
    RefreshIPLimit,
    SignupIPLimit,
    limit_login_account,
)
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
)
from app.schemas.user import UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignupRequest, db: DbDep, _: SignupIPLimit) -> UserOut:
    user = await auth_service.signup(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
    )
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenPair)
async def login(
    payload: LoginRequest, db: DbDep, request: Request, _: LoginIPLimit
) -> TokenPair:
    # Limited per source address and again per targeted account.
    await limit_login_account(request, payload.email)
    return await auth_service.login(db, email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshRequest, db: DbDep, _: RefreshIPLimit) -> TokenPair:
    return await auth_service.refresh(db, payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: DbDep) -> None:
    await auth_service.logout(db, payload.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
