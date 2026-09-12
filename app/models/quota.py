"""Per-user usage quota.

Tracks both a daily counter (free tier = 5/day) and a monthly counter for
longer-term reporting. Reset bookkeeping lives in
:mod:`app.services.quota_service`.
"""
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Quota(Base, TimestampMixin):
    __tablename__ = "quotas"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )

    daily_limit: Mapped[int] = mapped_column(
        Integer, default=settings.FREE_DAILY_LIMIT, nullable=False
    )
    used_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    day_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    monthly_limit: Mapped[int] = mapped_column(
        Integer, default=settings.FREE_MONTHLY_LIMIT, nullable=False
    )
    used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    month_reset_date: Mapped[datetime | None] = mapped_column(nullable=True)

    user: Mapped["User"] = relationship(back_populates="quota")
