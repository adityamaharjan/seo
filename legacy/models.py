from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base
from database import engine
from sqlalchemy.dialects.mysql import JSON

class SEOReport(Base):
    __tablename__ = "seo_reports"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(255), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255))
    dominant_keyword = Column(String(255))
    results = Column(JSON)  
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Users(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    

class Quotas(Base):
    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    monthly_limit = Column(Integer, default=100)  # Default quota
    used_quota = Column(Integer, default=0)
    reset_date = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)