"""Orchestration for user-supplied provider API keys.

Keys are validated against the provider before being stored, so a typo is
reported while the user is still looking at the form rather than silently
breaking an audit hours later.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.exceptions import BadRequestError, NotFoundError, ServiceUnavailableError
from app.core.logging import get_logger
from app.crud import api_key as api_key_crud
from app.models.api_key import ApiKeyProvider, UserApiKey
from app.schemas.api_key import ApiKeySettings, ApiKeyStatus
from app.seo import psi

logger = get_logger(__name__)

_HINT_LENGTH = 4


async def _validate_with_provider(provider: ApiKeyProvider, raw_key: str) -> None:
    if provider is ApiKeyProvider.google_psi:
        try:
            await psi.validate_key(raw_key)
        except psi.PsiKeyInvalidError as exc:
            raise BadRequestError(str(exc)) from exc


async def save(
    db: AsyncSession, *, user_id: int, provider: ApiKeyProvider, raw_key: str
) -> UserApiKey:
    if not crypto.is_available():
        raise ServiceUnavailableError(
            "This server cannot store API keys yet: the operator needs to set "
            "API_KEY_ENCRYPTION_KEY. Keys are never stored unencrypted."
        )

    await _validate_with_provider(provider, raw_key)

    row = await api_key_crud.upsert(
        db,
        user_id=user_id,
        provider=provider,
        encrypted_key=crypto.encrypt(raw_key),
        key_hint=raw_key[-_HINT_LENGTH:],
    )
    await db.commit()
    await db.refresh(row)
    # Deliberately logs the provider only — never the key or its hint.
    logger.info("api key saved", extra={"user_id": user_id, "provider": provider.value})
    return row


async def remove(
    db: AsyncSession, *, user_id: int, provider: ApiKeyProvider
) -> None:
    row = await api_key_crud.get(db, user_id, provider)
    if row is None:
        raise NotFoundError("No key stored for that provider.")
    await api_key_crud.delete(db, row)
    await db.commit()


async def get_key(
    db: AsyncSession, *, user_id: int, provider: ApiKeyProvider
) -> str | None:
    """Plaintext key for use against the provider, or None if unusable.

    None covers every case a caller must handle identically: no key stored, no
    encryption configured, or ciphertext that no longer matches the server key
    after an ``API_KEY_ENCRYPTION_KEY`` rotation.
    """
    row = await api_key_crud.get(db, user_id, provider)
    if row is None or not crypto.is_available():
        return None
    return crypto.decrypt(row.encrypted_key)


async def settings_for_user(db: AsyncSession, user_id: int) -> ApiKeySettings:
    """Status of every known provider, configured or not."""
    stored = {row.provider: row for row in await api_key_crud.list_for_user(db, user_id)}
    return ApiKeySettings(
        encryption_available=crypto.is_available(),
        providers=[
            ApiKeyStatus(
                provider=provider,
                configured=provider in stored,
                key_hint=getattr(stored.get(provider), "key_hint", None),
                last_used_at=getattr(stored.get(provider), "last_used_at", None),
                last_error=getattr(stored.get(provider), "last_error", None),
                updated_at=getattr(stored.get(provider), "updated_at", None),
            )
            for provider in ApiKeyProvider
        ],
    )
