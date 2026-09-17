"""Site audit models: one crawl, many analyzed pages.

Kept in their own tables rather than folded into ``seo_reports`` with a
discriminator column. A site audit and a single-page report are different
products with different lifecycles, and sharing one table would put a ``kind``
filter on every existing report query, where forgetting one silently mixes
crawled pages into a user's single-page history.
"""
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

# MySQL needs a length on any indexed string column, and a full 2048-char URL
# exceeds the key-length limit, so indexed URL columns are prefixed.
_JSON = JSON().with_variant(MySQLJSON(), "mysql")


class SiteAuditStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class PsiScope(enum.StrEnum):
    """How much of a crawl gets a PageSpeed run.

    A PSI call is 10-30 seconds per page per strategy and one unit of a 25k/day
    quota, so on a 50-page crawl this is the difference between a one-minute
    tail and an hour. It is a per-audit choice rather than a global setting
    because the right answer depends on the site, not the installation.
    """

    off = "off"
    homepage = "homepage"  # the crawl's start URL only
    # The first pages the crawl reaches. Discovery is breadth-first from the
    # start URL, so these are the shallowest pages — the ones most linked-to
    # and usually the ones that matter most.
    sample = "sample"
    all = "all"


# Pages given a PSI run under ``PsiScope.sample``.
PSI_SAMPLE_SIZE = 5


class SiteAudit(Base, TimestampMixin):
    __tablename__ = "site_audits"

    __table_args__ = (Index("ix_site_audits_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    start_url: Mapped[str] = mapped_column(String(2048))
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)

    status: Mapped[SiteAuditStatus] = mapped_column(
        Enum(SiteAuditStatus), default=SiteAuditStatus.pending, nullable=False, index=True
    )
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    quota_refunded: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("0")
    )
    # Whether the crawl ran PageSpeed Insights, and over how much of it. Stored
    # so a report can say which pages carry rendered metrics and which do not.
    used_psi: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default=text("0")
    )
    psi_scope: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # How many pages were asked for, versus what the crawl actually managed.
    max_pages: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    pages_crawled: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    pages_failed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default=text("0")
    )
    # "sitemap", "links", or "mixed": how the page list was discovered.
    discovery_source: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # Site-level averages, denormalized so the history list needs no join.
    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # The aggregate payload: category averages, ranked site-wide issues,
    # score spread, crawl errors.
    results: Mapped[dict | None] = mapped_column(_JSON, nullable=True)

    user: Mapped["User"] = relationship(back_populates="site_audits")
    pages: Mapped[list["SiteAuditPage"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SiteAuditPage.id",
    )


class SiteAuditPage(Base, TimestampMixin):
    __tablename__ = "site_audit_pages"

    __table_args__ = (Index("ix_site_audit_pages_audit_score", "audit_id", "overall_score"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    audit_id: Mapped[int] = mapped_column(
        ForeignKey("site_audits.id", ondelete="CASCADE"), index=True
    )

    url: Mapped[str] = mapped_column(String(2048))
    final_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_grade: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ttfb_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    load_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    issue_counts: Mapped[dict | None] = mapped_column(_JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The full per-page analysis, same shape as a single-page report's results,
    # so the page detail view reuses the existing report UI unchanged.
    results: Mapped[dict | None] = mapped_column(_JSON, nullable=True)

    audit: Mapped["SiteAudit"] = relationship(back_populates="pages")
