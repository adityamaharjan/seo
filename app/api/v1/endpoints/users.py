"""Self-service account endpoints: profile, password, quota, API keys."""
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbDep
from app.models.api_key import ApiKeyProvider
from app.schemas.api_key import ApiKeySettings, ApiKeyUpsert
from app.schemas.quota import QuotaOut
from app.schemas.user import PasswordChange, SessionsRevoked, UserOut, UserUpdate
from app.services import api_key_service, quota_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_profile(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_profile(payload: UserUpdate, user: CurrentUser, db: DbDep) -> UserOut:
    """Change your own username or email."""
    updated = await user_service.update_profile(
        db, user, username=payload.username, email=payload.email
    )
    return UserOut.model_validate(updated)


@router.post(
    "/me/password",
    response_model=SessionsRevoked,
    status_code=status.HTTP_200_OK,
)
async def change_password(
    payload: PasswordChange, user: CurrentUser, db: DbDep
) -> SessionsRevoked:
    """Change your password. Every existing session is signed out."""
    revoked = await user_service.change_password(
        db,
        user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return SessionsRevoked(revoked=revoked)


@router.get("/me/api-keys", response_model=ApiKeySettings)
async def list_api_keys(user: CurrentUser, db: DbDep) -> ApiKeySettings:
    """Which provider keys are configured. Never returns the keys themselves."""
    return await api_key_service.settings_for_user(db, user.id)


@router.put("/me/api-keys/{provider}", response_model=ApiKeySettings)
async def save_api_key(
    provider: ApiKeyProvider, payload: ApiKeyUpsert, user: CurrentUser, db: DbDep
) -> ApiKeySettings:
    """Store a provider key, after checking the provider accepts it."""
    await api_key_service.save(
        db, user_id=user.id, provider=provider, raw_key=payload.key
    )
    return await api_key_service.settings_for_user(db, user.id)


@router.delete("/me/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_api_key(
    provider: ApiKeyProvider, user: CurrentUser, db: DbDep
) -> None:
    await api_key_service.remove(db, user_id=user.id, provider=provider)


@router.get("/me/quota", response_model=QuotaOut)
async def get_quota(user: CurrentUser, db: DbDep) -> QuotaOut:
    quota = await quota_service.get_status(db, user.id)
    return QuotaOut(
        daily_limit=quota.daily_limit,
        used_today=quota.used_today,
        remaining_today=max(0, quota.daily_limit - quota.used_today),
        day_reset_date=quota.day_reset_date,
        monthly_limit=quota.monthly_limit,
        used_this_month=quota.used_this_month,
        month_reset_date=quota.month_reset_date,
    )
