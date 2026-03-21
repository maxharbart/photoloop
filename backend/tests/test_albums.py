import pytest
from httpx import AsyncClient

from app.models.album import Album
from app.models.photo import Photo
from app.models.project import Project
from app.models.user import User
from tests.conftest import get_token, auth_header


async def test_create_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.post(
        f"/api/projects/{project.slug}/albums",
        json={"name": "Vacation", "description": "Summer 2024"},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Vacation"
    assert data["description"] == "Summer 2024"


async def test_list_albums(
    client: AsyncClient,
    superuser: User,
    project: Project,
    db,
):
    album = Album(project_id=project.id, name="Album1")
    db.add(album)
    await db.commit()

    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/albums",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


async def test_add_photos_to_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
    db,
):
    album = Album(project_id=project.id, name="TestAlbum")
    db.add(album)
    await db.commit()
    await db.refresh(album)

    token = await get_token(client, "admin", "adminpass")
    photo_ids = [str(p.id) for p in sample_photos[:3]]
    resp = await client.post(
        f"/api/projects/{project.slug}/albums/{album.id}/photos",
        json={"photo_ids": photo_ids},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    assert resp.json()["added"] == 3


async def test_remove_photo_from_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
    db,
):
    from app.models.album import AlbumPhoto

    album = Album(project_id=project.id, name="RemTest")
    db.add(album)
    await db.commit()
    await db.refresh(album)

    ap = AlbumPhoto(album_id=album.id, photo_id=sample_photos[0].id, sort_order=0)
    db.add(ap)
    await db.commit()

    token = await get_token(client, "admin", "adminpass")
    resp = await client.delete(
        f"/api/projects/{project.slug}/albums/{album.id}/photos/{sample_photos[0].id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 204


async def test_reorder_photos_in_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photos: list[Photo],
    db,
):
    from app.models.album import AlbumPhoto

    album = Album(project_id=project.id, name="OrderTest")
    db.add(album)
    await db.commit()
    await db.refresh(album)

    for i, photo in enumerate(sample_photos[:3]):
        ap = AlbumPhoto(album_id=album.id, photo_id=photo.id, sort_order=i)
        db.add(ap)
    await db.commit()

    token = await get_token(client, "admin", "adminpass")
    # Reverse order
    reversed_ids = [str(p.id) for p in reversed(sample_photos[:3])]
    resp = await client.put(
        f"/api/projects/{project.slug}/albums/{album.id}/photos/order",
        json={"photo_ids": reversed_ids},
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    assert resp.json()["reordered"] == 3


async def test_delete_album(
    client: AsyncClient,
    superuser: User,
    project: Project,
    db,
):
    album = Album(project_id=project.id, name="ToDelete")
    db.add(album)
    await db.commit()
    await db.refresh(album)

    token = await get_token(client, "admin", "adminpass")
    resp = await client.delete(
        f"/api/projects/{project.slug}/albums/{album.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 204


async def test_album_nonmember_forbidden(
    client: AsyncClient,
    regular_user: User,
    project: Project,
):
    token = await get_token(client, "user1", "userpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/albums",
        headers=auth_header(token),
    )
    assert resp.status_code == 403
