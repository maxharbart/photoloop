import os

# Set test environment variables BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MEDIA_ROOT", "/tmp/test-media")
os.environ.setdefault("THUMBS_ROOT", "/tmp/test-thumbs")

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.models.project import Project, ProjectMember
from app.models.photo import Photo
from app.models.album import Album, AlbumPhoto
from app.routers.auth import hash_password

# Use an in-process SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True, scope="session")
def _enable_sqlite_fk():
    """Enable foreign keys for SQLite connections."""
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest.fixture
def app():
    """Return a patched FastAPI app with test DB override."""
    from app.main import app as _app
    from app.database import get_db

    async def _override_get_db():
        async with TestSession() as session:
            yield session

    _app.dependency_overrides[get_db] = _override_get_db
    yield _app
    _app.dependency_overrides.clear()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def superuser(db: AsyncSession) -> User:
    user = User(
        username="admin",
        hashed_password=hash_password("adminpass"),
        is_superuser=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def regular_user(db: AsyncSession) -> User:
    user = User(
        username="user1",
        hashed_password=hash_password("userpass"),
        is_superuser=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def project(db: AsyncSession) -> Project:
    proj = Project(
        slug="test-project",
        name="Test Project",
        source_path="test/photos",
        description="A test project",
    )
    db.add(proj)
    await db.commit()
    await db.refresh(proj)
    return proj


@pytest.fixture
async def project_with_member(
    db: AsyncSession, project: Project, regular_user: User
) -> Project:
    member = ProjectMember(
        project_id=project.id, user_id=regular_user.id, role="viewer"
    )
    db.add(member)
    await db.commit()
    return project


@pytest.fixture
async def project_with_owner(
    db: AsyncSession, project: Project, regular_user: User
) -> Project:
    member = ProjectMember(
        project_id=project.id, user_id=regular_user.id, role="owner"
    )
    db.add(member)
    await db.commit()
    return project


@pytest.fixture
async def sample_photo(db: AsyncSession, project: Project) -> Photo:
    photo = Photo(
        project_id=project.id,
        relative_path="2024/photo1.jpg",
        filename="photo1.jpg",
        taken_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        width=4000,
        height=3000,
        file_size=5_000_000,
        indexed_at=datetime.now(timezone.utc),
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


@pytest.fixture
async def sample_photos(db: AsyncSession, project: Project) -> list[Photo]:
    photos = []
    for i in range(5):
        photo = Photo(
            project_id=project.id,
            relative_path=f"2024/photo{i}.jpg",
            filename=f"photo{i}.jpg",
            taken_at=datetime(2024, 1 + i, 1, 12, 0, 0, tzinfo=timezone.utc),
            width=4000,
            height=3000,
            file_size=5_000_000,
            indexed_at=datetime.now(timezone.utc),
        )
        photos.append(photo)
        db.add(photo)
    await db.commit()
    for p in photos:
        await db.refresh(p)
    return photos


async def get_token(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
