import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import get_token, auth_header


async def test_login_success(client: AsyncClient, superuser: User):
    resp = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "adminpass"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, superuser: User):
    resp = await client.post(
        "/api/auth/login",
        data={"username": "admin", "password": "wrongpass"},
    )
    assert resp.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        data={"username": "nobody", "password": "pass"},
    )
    assert resp.status_code == 401


async def test_access_protected_without_token(client: AsyncClient):
    resp = await client.get("/api/projects")
    assert resp.status_code == 401


async def test_access_protected_with_invalid_token(client: AsyncClient):
    resp = await client.get(
        "/api/projects",
        headers={"Authorization": "Bearer invalid.token.here"},
    )
    assert resp.status_code == 401


async def test_register_as_superuser(client: AsyncClient, superuser: User):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.post(
        "/api/auth/register",
        json={"username": "newuser", "password": "newpass"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["is_superuser"] is False


async def test_register_as_regular_user_forbidden(
    client: AsyncClient, regular_user: User
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.post(
        "/api/auth/register",
        json={"username": "another", "password": "pass"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_register_duplicate_username(client: AsyncClient, superuser: User):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.post(
        "/api/auth/register",
        json={"username": "admin", "password": "pass"},
        headers=auth_header(token),
    )
    assert resp.status_code == 409
