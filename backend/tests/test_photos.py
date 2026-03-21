import pytest
from httpx import AsyncClient

from app.models.photo import Photo
from app.models.project import Project
from app.models.user import User
from tests.conftest import get_token, auth_header


async def test_list_photos_sorted_asc(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos?sort=asc",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    dates = [item["taken_at"] for item in data["items"]]
    assert dates == sorted(dates)


async def test_list_photos_sorted_desc(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos?sort=desc",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    dates = [item["taken_at"] for item in data["items"]]
    assert dates == sorted(dates, reverse=True)


async def test_list_photos_pagination(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos?page=1&page_size=2",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2

    # Page 3 should have 1 item
    resp = await client.get(
        f"/api/projects/{project.slug}/photos?page=3&page_size=2",
        headers=auth_header(token),
    )
    data = resp.json()
    assert len(data["items"]) == 1


async def test_list_photos_filter_by_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
    db,
):
    from app.models.album import Album, AlbumPhoto

    album = Album(project_id=project.id, name="Sel")
    db.add(album)
    await db.commit()
    await db.refresh(album)

    # Add only 2 photos to the album
    for i, photo in enumerate(sample_photos[:2]):
        ap = AlbumPhoto(album_id=album.id, photo_id=photo.id, sort_order=i)
        db.add(ap)
    await db.commit()

    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos?album_id={album.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


async def test_get_single_photo(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filename"] == "photo1.jpg"


async def test_get_photo_not_found(
    client: AsyncClient,
    superuser: User,
    project: Project,
):
    import uuid

    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos/{uuid.uuid4()}",
        headers=auth_header(token),
    )
    assert resp.status_code == 404


async def test_list_photos_nonmember_forbidden(
    client: AsyncClient,
    regular_user: User,
    project: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos",
        headers=auth_header(token),
    )
    assert resp.status_code == 403
