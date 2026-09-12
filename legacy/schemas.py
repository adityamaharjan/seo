from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, EmailStr, ConfigDict


# =========================
# USER SCHEMAS
# =========================

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =========================
# QUOTA SCHEMAS
# =========================

class QuotaOut(BaseModel):
    id: int
    user_id: int
    monthly_limit: int
    used_quota: int
    reset_date: Optional[datetime]
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# =========================
# SEO REPORT SCHEMAS
# =========================

class SEOReportCreate(BaseModel):
    url: str
    title: Optional[str] = None
    user_id: int
    dominant_keyword: Optional[str] = None
    results: Dict[str, Any]


class SEOReportOut(BaseModel):
    id: int
    url: str
    user_id: int
    title: Optional[str]
    dominant_keyword: Optional[str]
    results: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
