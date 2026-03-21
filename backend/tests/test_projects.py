import pytest
from httpx import AsyncClient

from app.models.project import Project
from app.models.user import User
from tests.conftest import get_token, auth_header


async def test_create_project_superuser(client: AsyncClient, superuser: User):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.post(
        "/api/projects",
        json={
            "slug": "new-proj",
            "name": "New Project",
            "source_path": "photos/new",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["slug"] == "new-proj"
    assert data["name"] == "New Project"


async def test_create_project_regular_user_forbidden(
    client: AsyncClient, regular_user: User
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.post(
        "/api/projects",
        json={
            "slug": "proj",
            "name": "Proj",
            "source_path": "photos",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_create_project_invalid_path(client: AsyncClient, superuser: User):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.post(
        "/api/projects",
        json={
            "slug": "bad",
            "name": "Bad",
            "source_path": "../../../etc",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_list_projects_superuser_sees_all(
    client: AsyncClient, superuser: User, project: Project
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get("/api/projects", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    slugs = [p["slug"] for p in data]
    assert "test-project" in slugs


async def test_list_projects_member_sees_own(
    client: AsyncClient,
    regular_user: User,
    project_with_member: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get("/api/projects", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["slug"] == "test-project"


async def test_list_projects_nonmember_sees_none(
    client: AsyncClient,
    regular_user: User,
    project: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get("/api/projects", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 0


async def test_get_project_nonmember_forbidden(
    client: AsyncClient,
    regular_user: User,
    project: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get(
        f"/api/projects/{project.slug}",
        headers=auth_header(token),
    )
    assert resp.status_code == 403


async def test_get_project_member_ok(
    client: AsyncClient,
    regular_user: User,
    project_with_member: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get(
        f"/api/projects/{project_with_member.slug}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["slug"] == "test-project"


async def test_update_project_owner(
    client: AsyncClient,
    regular_user: User,
    project_with_owner: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.put(
        f"/api/projects/{project_with_owner.slug}",
        json={"name": "Updated Name"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Name"


async def test_update_project_viewer_forbidden(
    client: AsyncClient,
    regular_user: User,
    project_with_member: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.put(
        f"/api/projects/{project_with_member.slug}",
        json={"name": "Nope"},
        headers=auth_header(token),
    )
    assert resp.status_code == 403
