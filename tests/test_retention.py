"""Nightly retention purge."""
from datetime import UTC, datetime, timedelta

import pytest

from app.core.config import settings
from app.crud import user as user_crud
from app.models.refresh_token import RefreshToken
from app.models.report import Report, ReportStatus
from app.services import retention_service


async def _make_user(db, name):
    return await user_crud.create(
        db, username=name, email=f"{name}@example.com", hashed_password="x"
    )


@pytest.mark.asyncio
async def test_old_reports_are_deleted_and_recent_ones_kept(session_factory):
    now = datetime.now(UTC)
    async with session_factory() as db:
        user = await _make_user(db, "keeper")
        db.add_all(
            [
                Report(
                    user_id=user.id,
                    url="https://old.example.com",
                    status=ReportStatus.done,
                    created_at=now - timedelta(days=settings.REPORT_RETENTION_DAYS + 5),
                    updated_at=now,
                ),
                Report(
                    user_id=user.id,
                    url="https://new.example.com",
                    status=ReportStatus.done,
                    created_at=now - timedelta(days=1),
                    updated_at=now,
                ),
            ]
        )
        await db.commit()

        removed = await retention_service.purge(db)
        assert removed["reports"] == 1

        remaining = (await db.execute(Report.__table__.select())).fetchall()
        assert len(remaining) == 1
        assert remaining[0].url == "https://new.example.com"


@pytest.mark.asyncio
async def test_revoked_and_expired_tokens_are_deleted(session_factory):
    now = datetime.now(UTC)
    async with session_factory() as db:
        user = await _make_user(db, "tokens")
        db.add_all(
            [
                RefreshToken(
                    user_id=user.id, jti="live", token_hash="a",
                    expires_at=now + timedelta(days=7), revoked=False,
                    created_at=now, updated_at=now,
                ),
                RefreshToken(
                    user_id=user.id, jti="revoked", token_hash="b",
                    expires_at=now + timedelta(days=7), revoked=True,
                    created_at=now, updated_at=now,
                ),
                RefreshToken(
                    user_id=user.id, jti="expired", token_hash="c",
                    expires_at=now - timedelta(days=settings.TOKEN_RETENTION_DAYS + 2),
                    revoked=False, created_at=now, updated_at=now,
                ),
            ]
        )
        await db.commit()

        removed = await retention_service.purge(db)
        assert removed["refresh_tokens"] == 2

        rows = (await db.execute(RefreshToken.__table__.select())).fetchall()
        assert [r.jti for r in rows] == ["live"]
