"""Aggregate router for API v1."""
from fastapi import APIRouter

from app.api.v1.endpoints import admin, analyses, auth, health, site_audits, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(analyses.router)
api_router.include_router(site_audits.router)
api_router.include_router(health.router)
