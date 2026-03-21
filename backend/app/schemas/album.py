import uuid
from datetime import datetime

from pydantic import BaseModel


class AlbumCreate(BaseModel):
    name: str
    description: str | None = None


class AlbumUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_photo_id: uuid.UUID | None = None


class AlbumOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    cover_photo_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlbumPhotosAdd(BaseModel):
    photo_ids: list[uuid.UUID]


class AlbumPhotosOrder(BaseModel):
    photo_ids: list[uuid.UUID]
