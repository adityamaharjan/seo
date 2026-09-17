"""Application configuration loaded from environment variables.

Uses pydantic-settings so all runtime configuration is declared, typed and
validated in one place. Import the cached ``settings`` singleton via
``get_settings()``.
"""
import re
from functools import lru_cache
from typing import Annotated

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEFAULT_JWT_SECRET = "CHANGE_ME_IN_PRODUCTION"

# Origins matched by regex are as trusted as ones listed literally, so a loose
# pattern is the same mistake as a wildcard, just harder to notice.
_CATCH_ALL_REGEXES = {".*", "^.*$", ".+", "^.+$", "^.*", ".*$"}


def _origin_regex_problems(pattern: str) -> list[str]:
    problems: list[str] = []
    stripped = pattern.strip()
    if stripped in _CATCH_ALL_REGEXES:
        problems.append(
            "CORS_ORIGIN_REGEX matches every origin, which is a wildcard by another name."
        )
        return problems
    if not stripped.startswith("^") or not stripped.endswith("$"):
        problems.append(
            "CORS_ORIGIN_REGEX must be anchored with ^ and $, otherwise it matches "
            "any origin that merely contains the pattern."
        )
    if "https://" not in stripped and "http://" not in stripped:
        problems.append("CORS_ORIGIN_REGEX should include the scheme, e.g. ^https://...$")
    return problems


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "SEO Analysis API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database (env names kept backwards-compatible with the prototype) ---
    DB: str = Field(default="seo", alias="DB")
    DBUser: str = Field(default="seo_admin", alias="DBUser")
    DBPassword: str = Field(default="", alias="DBPassword")
    DBPort: int = Field(default=3306, alias="DBPort")
    DB_HOST: str = Field(default="localhost", alias="DB_HOST")
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # --- Redis / ARQ ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth / JWT ---
    JWT_SECRET: str = f"{_DEFAULT_JWT_SECRET}_USE_A_LONG_RANDOM_STRING"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Quota (free tier) ---
    FREE_DAILY_LIMIT: int = 5
    FREE_MONTHLY_LIMIT: int = 100

    # --- Rate limiting (auth endpoints; backed by Redis) ---
    RATE_LIMIT_ENABLED: bool = True
    LOGIN_RATE_LIMIT: int = 10       # attempts per window, per IP+email
    LOGIN_RATE_WINDOW_SECONDS: int = 300
    SIGNUP_RATE_LIMIT: int = 5       # accounts per window, per IP
    SIGNUP_RATE_WINDOW_SECONDS: int = 3600

    # --- Retention (nightly purge job in the worker) ---
    REPORT_RETENTION_DAYS: int = 90  # 0 disables report pruning
    TOKEN_RETENTION_DAYS: int = 7    # grace period after a refresh token expires

    # --- CORS ---
    CORS_ORIGINS: Annotated[list[str], NoDecode] = ["*"]
    # Optional anchored regex for origins that cannot be listed literally, such
    # as the per-branch preview URLs Vercel and Cloudflare Pages generate.
    # Example: ^https://seo-frontend(-[a-z0-9-]+)?\.vercel\.app$
    CORS_ORIGIN_REGEX: str | None = None
    # Response headers the browser is allowed to read cross-origin. Retry-After
    # carries the quota and rate-limit reset, and without it the frontend can
    # see the 429 but not when to try again.
    CORS_EXPOSE_HEADERS: Annotated[list[str], NoDecode] = [
        "Retry-After",
        "X-Request-ID",
        "X-Process-Time-ms",
    ]

    # --- User-supplied API keys (BYOK) ---
    # Fernet key encrypting per-user provider keys at rest. Generate with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Left empty, key storage is refused outright rather than falling back to
    # plaintext, so BYOK features are simply unavailable until it is set.
    # Rotating it makes every stored key undecryptable; users must re-enter them.
    API_KEY_ENCRYPTION_KEY: str = ""

    # Local-development fallback PSI key. Outside production, a user with no
    # stored key of their own falls back to this one so PageSpeed features can
    # be exercised without registering a Google Cloud project per developer.
    # It is ignored in production: there, PSI is strictly bring-your-own-key,
    # because a server-wide key would put every user's audits on one 25k/day
    # quota and one bill.
    GOOGLE_PAGE_SPEED_INSIGHTS_API_KEY: str = ""

    # --- SEO engine limits ---
    SEO_TIMEOUT_SECONDS: int = 15
    SEO_MAX_PAGE_BYTES: int = 5_000_000  # 5 MB hard cap on fetched HTML
    SEO_MAX_BROKEN_LINK_CHECKS: int = 25  # cap outbound HEAD requests per analysis
    SEO_USER_AGENT: str = (
        "Mozilla/5.0 (Compatible; FlatSEO/1.0; +https://seo.hakezlabs.qzz.io)"
    )
    SEO_MAX_REDIRECTS: int = 10
    # Escape hatch for analyzing sites on the local/private network. Leaving
    # this on in production turns the API into a proxy into your own network.
    SEO_ALLOW_PRIVATE_TARGETS: bool = False

    # --- Site audit (multi-page crawl) ---
    # Hard ceiling on pages per crawl. The submit form offers a choice up to
    # this number; anything higher is rejected rather than silently truncated.
    SITE_AUDIT_MAX_PAGES: int = 50
    SITE_AUDIT_DEFAULT_PAGES: int = 10
    # Pages analyzed at once. Each one is a full analysis with its own outbound
    # requests, so this multiplies the load a single audit puts on a host.
    SITE_AUDIT_CONCURRENCY: int = 4
    # Whole-crawl budget. A 50-page audit of a slow host must still finish
    # rather than occupying a worker slot indefinitely.
    SITE_AUDIT_TIMEOUT_SECONDS: int = 900
    # Sitemap URLs fetched while discovering pages, including index expansion.
    SITE_AUDIT_MAX_SITEMAPS: int = 10
    # Links probed per page during a crawl. The single-page default (25) would
    # multiply by the page concurrency into ~100 simultaneous requests at one
    # host, which reads as an attack and gets rate-limited into false positives.
    SITE_AUDIT_BROKEN_LINK_CHECKS: int = 5

    # --- PageSpeed Insights ---
    # A PSI run is a real Lighthouse execution on Google's infrastructure, so
    # it takes far longer than any other call the analyzer makes.
    PSI_TIMEOUT_SECONDS: int = 90
    # Strategies run per URL. Mobile is what Google ranks on; desktop is worth
    # having alongside it, at double the time and quota.
    PSI_STRATEGIES: Annotated[list[str], NoDecode] = ["mobile", "desktop"]
    # Concurrent PSI calls per audit. PSI allows 240 queries/minute per key, so
    # the binding constraint is the audit's own wall-clock budget, not the API.
    PSI_CONCURRENCY: int = 6

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in {"production", "prod"}

    @model_validator(mode="after")
    def _guard_production_config(self) -> "Settings":
        """Refuse to boot with development defaults in production.

        These are the settings that are harmless locally and dangerous when
        exposed, so failing loudly at startup beats discovering them later.
        """
        if not self.is_production:
            return self

        problems: list[str] = []
        if _DEFAULT_JWT_SECRET in self.JWT_SECRET or len(self.JWT_SECRET) < 32:
            problems.append(
                "JWT_SECRET is unset, the built-in default, or shorter than 32 chars. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if "*" in self.CORS_ORIGINS and not self.CORS_ORIGIN_REGEX:
            problems.append(
                "CORS_ORIGINS is a wildcard. Because credentials are allowed, this "
                "reflects back any origin that asks. List your frontend origins explicitly."
            )
        if self.CORS_ORIGIN_REGEX:
            problems.extend(_origin_regex_problems(self.CORS_ORIGIN_REGEX))
        if self.SEO_ALLOW_PRIVATE_TARGETS:
            problems.append(
                "SEO_ALLOW_PRIVATE_TARGETS is on, which lets any user make the server "
                "fetch private network addresses."
            )
        if not self.API_KEY_ENCRYPTION_KEY:
            problems.append(
                "API_KEY_ENCRYPTION_KEY is unset, so users cannot store the provider "
                "API keys that PageSpeed Insights features need. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        if self.DEBUG:
            problems.append("DEBUG is on.")

        if problems:
            raise ValueError(
                "Unsafe configuration for ENVIRONMENT=production:\n  - "
                + "\n  - ".join(problems)
            )
        return self

    @field_validator("CORS_ORIGINS", "CORS_EXPOSE_HEADERS", "PSI_STRATEGIES", mode="before")
    @classmethod
    def _split_list(cls, v):
        """Accept both a comma-separated string and a real list.

        These are annotated NoDecode so the raw environment string arrives here
        intact. Without that, pydantic-settings tries to JSON-decode the value
        and a documented setting like ``CORS_ORIGINS=https://app.example.com``
        crashes the process at startup.
        """
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("API_KEY_ENCRYPTION_KEY")
    @classmethod
    def _validate_encryption_key(cls, v: str) -> str:
        """Reject a malformed Fernet key at boot rather than on first use.

        A bad value here would otherwise surface as an error the first time a
        user tries to save an API key, long after deployment.
        """
        if not v.strip():
            return ""
        from cryptography.fernet import Fernet

        try:
            Fernet(v.encode())
        except Exception as exc:
            raise ValueError(
                "API_KEY_ENCRYPTION_KEY is not a valid Fernet key. Generate one with: "
                'python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            ) from exc
        return v

    @field_validator("CORS_ORIGIN_REGEX")
    @classmethod
    def _validate_origin_regex(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"CORS_ORIGIN_REGEX is not a valid regex: {exc}") from exc
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL using the asyncmy driver."""
        return (
            f"mysql+asyncmy://{self.DBUser}:{self.DBPassword}"
            f"@{self.DB_HOST}:{self.DBPort}/{self.DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Sync URL (PyMySQL) used by Alembic's offline/online migrations."""
        return (
            f"mysql+pymysql://{self.DBUser}:{self.DBPassword}"
            f"@{self.DB_HOST}:{self.DBPort}/{self.DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
