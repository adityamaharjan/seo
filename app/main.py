"""FastAPI application factory and ASGI entrypoint.

Run with::

    uvicorn app.main:app --reload
"""
import time
import uuid
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.docs_pages import router as docs_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    app.state.arq = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    logger.info("application started", extra={"env": settings.ENVIRONMENT})
    try:
        yield
    finally:
        await app.state.arq.close()
        from app.db.session import engine

        await engine.dispose()
        logger.info("application stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Production SEO analysis API with auth, quotas and background jobs.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_origin_regex=settings.CORS_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Without this the browser hides Retry-After cross-origin, so a
        # frontend on another domain could see a 429 but not when to retry.
        expose_headers=settings.CORS_EXPOSE_HEADERS,
    )
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.middleware("http")
    async def add_request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-ms"] = str(elapsed_ms)
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(docs_router)  # /documentation (rendered Markdown)

    @app.get("/", tags=["root"])
    async def root() -> dict:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "swagger": "/docs",
            "redoc": "/redoc",
            "documentation": "/documentation",
        }

    return app


app = create_app()
