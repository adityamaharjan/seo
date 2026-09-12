"""User schemas: profile, password change, and the admin management views."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.user import UserRole


class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Self-service profile edit. Omitted fields are left alone."""

    username: str | None = Field(default=None, min_length=3, max_length=50)
    email: EmailStr | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "UserUpdate":
        if self.username is None and self.email is None:
            raise ValueError("Provide a username or an email to change.")
        return self


class PasswordChange(BaseModel):
    """Changing a password requires proving you know the current one."""

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _must_differ(self) -> "PasswordChange":
        if self.current_password == self.new_password:
            raise ValueError("The new password must differ from the current one.")
        return self


class UserQuotaSummary(BaseModel):
    daily_limit: int
    used_today: int
    monthly_limit: int
    used_this_month: int
    day_reset_date: date | None


class UserDetail(UserOut):
    """A single user as an administrator sees them."""

    updated_at: datetime
    report_count: int
    quota: UserQuotaSummary | None


class PaginatedUsers(BaseModel):
    items: list[UserDetail]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    """Role and status changes. Omitted fields are left alone."""

    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "AdminUserUpdate":
        if self.role is None and self.is_active is None:
            raise ValueError("Provide a role or an active flag to change.")
        return self


class AdminQuotaUpdate(BaseModel):
    """Per-user allowance override. Omitted fields are left alone."""

    daily_limit: int | None = Field(default=None, ge=0, le=100_000)
    monthly_limit: int | None = Field(default=None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "AdminQuotaUpdate":
        if self.daily_limit is None and self.monthly_limit is None:
            raise ValueError("Provide a daily or monthly limit to change.")
        return self


class SessionsRevoked(BaseModel):
    revoked: int
