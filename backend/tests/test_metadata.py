import pytest
from unittest.mock import patch
from httpx import AsyncClient

from app.models.photo import Photo
from app.models.project import Project
from app.models.user import User
from tests.conftest import get_token, auth_header


@patch("app.routers.metadata.write_metadata_to_file")
async def test_patch_metadata_updates_db(
    mock_task,
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    mock_task.delay.return_value = None

    token = await get_token(client, "admin", "adminpass")
    resp = await client.patch(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/metadata",
        json={
            "taken_at": "2024-07-20T10:30:00Z",
            "gps_lat": 48.8566,
            "gps_lon": 2.3522,
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "updated"
    mock_task.delay.assert_called_once()


@patch("app.routers.metadata.write_metadata_to_file")
async def test_patch_metadata_partial_update(
    mock_task,
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    mock_task.delay.return_value = None

    token = await get_token(client, "admin", "adminpass")
    resp = await client.patch(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/metadata",
        json={"taken_at": "2024-12-25T00:00:00Z"},
        headers=auth_header(token),
    )
    assert resp.status_code == 200


async def test_patch_metadata_invalid_lat(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.patch(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/metadata",
        json={"gps_lat": 999.0},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


async def test_patch_metadata_invalid_lon(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.patch(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/metadata",
        json={"gps_lon": -200.0},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


async def test_patch_metadata_nonmember_forbidden(
    client: AsyncClient,
    regular_user: User,
    project: Project,
    sample_photo: Photo,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.patch(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/metadata",
        json={"gps_lat": 10.0},
        headers=auth_header(token),
    )
    assert resp.status_code == 403
