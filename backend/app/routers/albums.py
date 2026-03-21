import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.album import Album, AlbumPhoto
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.projects import _get_project_by_slug, _require_member
from app.schemas.album import AlbumCreate, AlbumUpdate, AlbumOut, AlbumPhotosAdd, AlbumPhotosOrder

router = APIRouter(prefix="/api/projects/{slug}/albums", tags=["albums"])


@router.get("", response_model=list[AlbumOut])
async def list_albums(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    result = await db.execute(select(Album).where(Album.project_id == project.id))
    return result.scalars().all()


@router.post("", response_model=AlbumOut, status_code=201)
async def create_album(
    slug: str,
    body: AlbumCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    album = Album(project_id=project.id, **body.model_dump())
    db.add(album)
    await db.commit()
    await db.refresh(album)
    return album


async def _get_album(album_id: uuid.UUID, project_id: uuid.UUID, db: AsyncSession) -> Album:
    album = await db.get(Album, album_id)
    if album is None or album.project_id != project_id:
        raise HTTPException(status_code=404, detail="Album not found")
    return album


@router.get("/{album_id}", response_model=AlbumOut)
async def get_album(
    slug: str,
    album_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    return await _get_album(album_id, project.id, db)


@router.put("/{album_id}", response_model=AlbumOut)
async def update_album(
    slug: str,
    album_id: uuid.UUID,
    body: AlbumUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    album = await _get_album(album_id, project.id, db)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(album, key, value)
    await db.commit()
    await db.refresh(album)
    return album


@router.delete("/{album_id}", status_code=204)
async def delete_album(
    slug: str,
    album_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    album = await _get_album(album_id, project.id, db)
    await db.delete(album)
    await db.commit()


@router.post("/{album_id}/photos", status_code=201)
async def add_photos_to_album(
    slug: str,
    album_id: uuid.UUID,
    body: AlbumPhotosAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    await _get_album(album_id, project.id, db)

    # Get current max sort_order
    result = await db.execute(
        select(AlbumPhoto.sort_order)
        .where(AlbumPhoto.album_id == album_id)
        .order_by(AlbumPhoto.sort_order.desc())
        .limit(1)
    )
    max_order = result.scalar() or 0

    for i, photo_id in enumerate(body.photo_ids):
        ap = AlbumPhoto(album_id=album_id, photo_id=photo_id, sort_order=max_order + i + 1)
        db.add(ap)
    await db.commit()
    return {"added": len(body.photo_ids)}


@router.delete("/{album_id}/photos/{photo_id}", status_code=204)
async def remove_photo_from_album(
    slug: str,
    album_id: uuid.UUID,
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    result = await db.execute(
        select(AlbumPhoto).where(
            AlbumPhoto.album_id == album_id,
            AlbumPhoto.photo_id == photo_id,
        )
    )
    ap = result.scalar_one_or_none()
    if ap is None:
        raise HTTPException(status_code=404, detail="Photo not in album")
    await db.delete(ap)
    await db.commit()


@router.put("/{album_id}/photos/order", status_code=200)
async def reorder_photos(
    slug: str,
    album_id: uuid.UUID,
    body: AlbumPhotosOrder,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    await _get_album(album_id, project.id, db)

    for i, photo_id in enumerate(body.photo_ids):
        result = await db.execute(
            select(AlbumPhoto).where(
                AlbumPhoto.album_id == album_id,
                AlbumPhoto.photo_id == photo_id,
            )
        )
        ap = result.scalar_one_or_none()
        if ap:
            ap.sort_order = i
    await db.commit()
    return {"reordered": len(body.photo_ids)}
