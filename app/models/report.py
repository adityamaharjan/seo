"""SEO analysis report model."""
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ReportStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class Report(Base, TimestampMixin):
    __tablename__ = "seo_reports"

    # The history endpoint filters by user and orders by recency; the composite
    # index serves both halves of that query.
    __table_args__ = (Index("ix_seo_reports_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048), index=True)
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)

    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus), default=ReportStatus.pending, nullable=False, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set once when a failed analysis returns its quota unit, so an ARQ retry
    # cannot refund the same report twice.
    quota_refunded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("0")
    )

    # Summary fields denormalized for cheap listing / sorting.
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Keywords the submitter asked this page to be judged against, kept so the
    # worker can score placement and the report can show what was targeted.
    target_keywords: Mapped[list | None] = mapped_column(
        JSON().with_variant(MySQLJSON(), "mysql"), nullable=True
    )
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full structured result payload: MySQL native JSON, generic JSON elsewhere
    # (e.g. SQLite in tests).
    results: Mapped[dict | None] = mapped_column(
        JSON().with_variant(MySQLJSON(), "mysql"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="reports")
