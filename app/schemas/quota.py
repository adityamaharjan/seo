"""Quota schemas."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class QuotaOut(BaseModel):
    daily_limit: int
    used_today: int
    remaining_today: int
    day_reset_date: date | None
    monthly_limit: int
    used_this_month: int
    month_reset_date: datetime | None

    model_config = ConfigDict(from_attributes=True)
