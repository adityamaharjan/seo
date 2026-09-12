"""User-supplied provider API keys (BYOK)."""
import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ApiKeyProvider(enum.StrEnum):
    google_psi = "google_psi"


class UserApiKey(Base, TimestampMixin):
    __tablename__ = "user_api_keys"

    # One key per provider per user; saving again replaces the stored value.
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_user_api_keys_user_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[ApiKeyProvider] = mapped_column(
        Enum(ApiKeyProvider), nullable=False
    )

    # Fernet ciphertext. Never returned by the API and never logged.
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    # Trailing characters of the plaintext, so the UI can show which key is
    # stored without being able to reconstruct it.
    key_hint: Mapped[str | None] = mapped_column(String(8), nullable=True)

    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Most recent provider rejection (quota, invalid key), surfaced in settings
    # so a silently-broken key is visible before the next audit runs.
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped["User"] = relationship(back_populates="api_keys")
