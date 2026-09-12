"""Model registry for Alembic.

Importing this module pulls in every ORM model so that ``Base.metadata`` and
Alembic autogenerate see the full schema.
"""
from app.db.base_class import Base, TimestampMixin  # noqa: F401
from app.models.api_key import UserApiKey  # noqa: E402,F401
from app.models.quota import Quota  # noqa: E402,F401
from app.models.refresh_token import RefreshToken  # noqa: E402,F401
from app.models.report import Report  # noqa: E402,F401
from app.models.site_audit import SiteAudit, SiteAuditPage  # noqa: E402,F401

# Import models so they register with Base.metadata.
from app.models.user import User  # noqa: E402,F401
