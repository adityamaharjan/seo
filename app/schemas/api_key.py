"""Schemas for user-supplied provider API keys.

The stored key itself is never part of a response — only whether one exists,
a short hint, and how it last behaved.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.api_key import ApiKeyProvider


class ApiKeyUpsert(BaseModel):
    key: str

    @field_validator("key")
    @classmethod
    def _clean(cls, v: str) -> str:
        key = v.strip()
        if not key:
            raise ValueError("API key cannot be empty.")
        if len(key) > 512:
            raise ValueError("That does not look like an API key (too long).")
        return key


class ApiKeyStatus(BaseModel):
    provider: ApiKeyProvider
    configured: bool
    key_hint: str | None = None
    last_used_at: datetime | None = None
    last_error: str | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApiKeySettings(BaseModel):
    """Every known provider, so the UI can render a row per provider."""

    # False when the server has no API_KEY_ENCRYPTION_KEY, in which case keys
    # cannot be stored at all and the UI explains why rather than failing later.
    encryption_available: bool
    providers: list[ApiKeyStatus]
