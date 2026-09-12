"""ARQ worker configuration.

Run with::

    arq app.workers.settings.WorkerSettings
"""
from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings
from app.core.logging import configure_logging
from app.workers.tasks import (
    purge_old_data_task,
    run_analysis_task,
    run_site_audit_task,
)


async def startup(ctx: dict) -> None:
    configure_logging()


async def shutdown(ctx: dict) -> None:
    pass


class WorkerSettings:
    functions = [run_analysis_task, run_site_audit_task, purge_old_data_task]
    # Retention sweep at 03:17 UTC; off-peak and offset from the hour so it
    # does not collide with every other nightly job on the box.
    cron_jobs = [cron(purge_old_data_task, hour=3, minute=17)]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 10
    # A site audit crawls many pages, so the timeout has to cover the whole
    # crawl budget rather than a single fetch.
    job_timeout = settings.SITE_AUDIT_TIMEOUT_SECONDS + 120
    keep_result = 3600
