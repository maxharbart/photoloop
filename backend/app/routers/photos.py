import uuid

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.photo import Photo
from app.models.album import AlbumPhoto
from app.models.project import Project
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.projects import _get_project_by_slug, _require_member, _require_owner
from app.schemas.photo import PhotoOut, PhotoListResponse, ScanResponse, ScanStatusResponse

router = APIRouter(prefix="/api/projects/{slug}/photos", tags=["photos"])


def _photo_to_out(photo: Photo) -> PhotoOut:
    return PhotoOut(
        id=photo.id,
        project_id=photo.project_id,
        relative_path=photo.relative_path,
        filename=photo.filename,
        taken_at=photo.taken_at,
        gps_lat=photo.gps_lat,
        gps_lon=photo.gps_lon,
        location_name=photo.location_name,
        width=photo.width,
        height=photo.height,
        file_size=photo.file_size,
        thumb_sm_url=f"/thumbs/{photo.thumb_sm}" if photo.thumb_sm else None,
        thumb_md_url=f"/thumbs/{photo.thumb_md}" if photo.thumb_md else None,
        indexed_at=photo.indexed_at,
    )


@router.get("", response_model=PhotoListResponse)
async def list_photos(
    slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sort: str = Query("asc", pattern="^(asc|desc)$"),
    album_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)

    query = select(Photo).where(Photo.project_id == project.id)
    count_query = select(func.count(Photo.id)).where(Photo.project_id == project.id)

    if album_id:
        query = query.join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id).where(
            AlbumPhoto.album_id == album_id
        )
        count_query = count_query.join(AlbumPhoto, AlbumPhoto.photo_id == Photo.id).where(
            AlbumPhoto.album_id == album_id
        )
        query = query.order_by(AlbumPhoto.sort_order)
    else:
        order = Photo.taken_at.asc() if sort == "asc" else Photo.taken_at.desc()
        query = query.order_by(order)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await db.execute(query)
    photos = result.scalars().all()

    return PhotoListResponse(
        items=[_photo_to_out(p) for p in photos],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{photo_id}", response_model=PhotoOut)
async def get_photo(
    slug: str,
    photo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)

    photo = await db.get(Photo, photo_id)
    if photo is None or photo.project_id != project.id:
        raise HTTPException(status_code=404, detail="Photo not found")
    return _photo_to_out(photo)


scan_router = APIRouter(prefix="/api/projects/{slug}/scan", tags=["scan"])


@scan_router.post("", response_model=ScanResponse)
async def trigger_scan(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_owner(project, current_user, db)

    from app.services.scanner import scan_project
    task = scan_project.delay(str(project.id), project.source_path)
    return ScanResponse(task_id=task.id)


@scan_router.get("/{task_id}", response_model=ScanStatusResponse)
async def scan_status(
    slug: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)

    result = AsyncResult(task_id)
    return ScanStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() else None,
    )
