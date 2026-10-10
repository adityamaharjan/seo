"""Pytest fixtures: in-memory async DB, ASGI client, dependency overrides."""
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.api.deps import get_arq
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class FakeArq:
    """Records enqueue calls so analysis lifecycle can be driven manually."""

    def __init__(self) -> None:
        self.jobs: list[tuple] = []

    async def enqueue_job(self, name: str, *args):
        self.jobs.append((name, args))

        class _Job:
            job_id = f"job-{len(self.jobs)}"

        return _Job()

    async def ping(self) -> bool:
        return True


@pytest_asyncio.fixture
async def fake_arq() -> FakeArq:
    return FakeArq()


@pytest_asyncio.fixture
async def client(
    session_factory, fake_arq
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app()

    async def _get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_arq] = lambda: fake_arq

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient) -> dict:
    await client.post(
        "/api/v1/auth/signup",
        json={
            "username": "tester",
            "email": "tester@example.com",
            "password": "supersecret123",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "supersecret123"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _register(client: AsyncClient, username: str, email: str, password: str) -> dict:
    """Sign up and return Authorization headers for the new account."""
    await client.post(
        "/api/v1/auth/signup",
        json={"username": username, "email": email, "password": password},
    )
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest_asyncio.fixture
async def make_user(client: AsyncClient):
    """Factory for extra accounts, so tests can act as more than one person."""

    async def _make(username: str, email: str, password: str = "supersecret123") -> dict:
        return await _register(client, username, email, password)

    return _make


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, session_factory) -> dict:
    """An administrator. The first admin cannot be made through the API."""
    from sqlalchemy import select

    from app.models.user import User, UserRole

    headers = await _register(client, "boss", "boss@example.com", "supersecret123")
    async with session_factory() as db:
        res = await db.execute(select(User).where(User.email == "boss@example.com"))
        user = res.scalar_one()
        user.role = UserRole.admin
        await db.commit()
    return headers
