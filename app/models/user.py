"""User account model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.api_key import UserApiKey
    from app.models.quota import Quota
    from app.models.refresh_token import RefreshToken
    from app.models.report import Report
    from app.models.site_audit import SiteAudit


class UserRole(enum.StrEnum):
    user = "user"
    admin = "admin"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(Text)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.user, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    quota: Mapped["Quota"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    site_audits: Mapped[list["SiteAudit"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["UserApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
