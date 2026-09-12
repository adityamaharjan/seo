"""Liveness and readiness probes."""
from fastapi import APIRouter, Request
from sqlalchemy import text

from app.api.deps import DbDep
from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": settings.APP_VERSION}


@router.get("/ready")
async def ready(request: Request, db: DbDep) -> dict:
    checks = {"database": False, "redis": False}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass
    try:
        arq = getattr(request.app.state, "arq", None)
        if arq is not None:
            await arq.ping()
            checks["redis"] = True
    except Exception:
        pass
    ok = all(checks.values())
    return {"status": "ready" if ok else "degraded", "checks": checks}
