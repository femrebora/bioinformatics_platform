"""
Pytest fixtures for the bioinformatics platform backend.

Uses:
  - SQLite (aiosqlite) in-memory database — no Postgres needed
  - FastAPI TestClient (httpx ASGITransport)
  - JWT auth bypass via dependency override
"""
import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.user import User
from app.services.auth import create_access_token, hash_password

# ── In-memory SQLite test database ────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def create_tables():
    """Create all tables once per test session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    """Provide a fresh DB session per test with rollback on teardown."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# ── Override get_db to use the test database ───────────────────────────────

async def _override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = _override_get_db


# ── Test user + auth token ─────────────────────────────────────────────────

TEST_USER_EMAIL    = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"
TEST_USER_ID       = "test-user-id-0001"


@pytest_asyncio.fixture(scope="session")
async def test_user():
    """Create a test user in the DB once per session."""
    async with TestSessionLocal() as session:
        user = User(
            id=TEST_USER_ID,
            email=TEST_USER_EMAIL,
            hashed_password=hash_password(TEST_USER_PASSWORD),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


@pytest.fixture(scope="session")
def auth_token(test_user):
    """Return a valid JWT for the test user."""
    # test_user fixture is async; we call the sync token factory directly
    return create_access_token(TEST_USER_ID)


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ── Async HTTP client ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    """Return an async HTTPX client connected to the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
