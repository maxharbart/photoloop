import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.photo import Photo
from app.models.user import User
from app.routers.auth import get_current_user
from app.routers.projects import _get_project_by_slug, _require_member

router = APIRouter(prefix="/api/projects/{slug}/photos/{photo_id}/metadata", tags=["metadata"])


class MetadataUpdate(BaseModel):
    taken_at: datetime | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None

    @field_validator("gps_lat")
    @classmethod
    def validate_lat(cls, v):
        if v is not None and (v < -90 or v > 90):
            raise ValueError("Latitude must be between -90 and 90")
        return v

    @field_validator("gps_lon")
    @classmethod
    def validate_lon(cls, v):
        if v is not None and (v < -180 or v > 180):
            raise ValueError("Longitude must be between -180 and 180")
        return v


@router.patch("")
async def update_metadata(
    slug: str,
    photo_id: uuid.UUID,
    body: MetadataUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)

    photo = await db.get(Photo, photo_id)
    if photo is None or photo.project_id != project.id:
        raise HTTPException(status_code=404, detail="Photo not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(photo, key, value)
    await db.commit()
    await db.refresh(photo)

    # Enqueue EXIF write task
    from app.services.exif import write_metadata_to_file
    write_metadata_to_file.delay(str(photo.id))

    return {"status": "updated", "photo_id": str(photo.id)}
