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


async def test_video_stream_returns_x_accel_redirect(
    client: AsyncClient,
    superuser: User,
    project: Project,
    db,
):
    from datetime import datetime, timezone

    video = Photo(
        project_id=project.id,
        relative_path="2024/clip.mp4",
        filename="clip.mp4",
        taken_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        width=1920,
        height=1080,
        file_size=10_000_000,
        media_type="video",
        duration=30.5,
        indexed_at=datetime.now(timezone.utc),
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos/{video.id}/stream",
        headers=auth_header(token),
        follow_redirects=False,
    )
    assert resp.status_code == 200
    assert "X-Accel-Redirect" in resp.headers
    assert resp.headers["X-Accel-Redirect"] == f"/internal-media/{project.source_path}/2024/clip.mp4"


async def test_video_stream_rejects_photo(
    client: AsyncClient,
    superuser: User,
    project: Project,
    sample_photo: Photo,
):
    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos/{sample_photo.id}/stream",
        headers=auth_header(token),
    )
    assert resp.status_code == 400


async def test_photo_response_includes_video_fields(
    client: AsyncClient,
    superuser: User,
    project: Project,
    db,
):
    from datetime import datetime, timezone

    video = Photo(
        project_id=project.id,
        relative_path="2024/video.mp4",
        filename="video.mp4",
        taken_at=datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        width=1920,
        height=1080,
        file_size=10_000_000,
        media_type="video",
        duration=60.0,
        indexed_at=datetime.now(timezone.utc),
    )
    db.add(video)
    await db.commit()
    await db.refresh(video)

    token = await get_token(client, "admin", "adminpass")
    resp = await client.get(
        f"/api/projects/{project.slug}/photos/{video.id}",
        headers=auth_header(token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["media_type"] == "video"
    assert data["duration"] == 60.0
    assert data["original_url"] is not None
    assert "/stream" in data["original_url"]
