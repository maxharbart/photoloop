import uuid
from datetime import datetime

from pydantic import BaseModel


class PhotoOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    relative_path: str
    filename: str
    taken_at: datetime | None
    gps_lat: float | None
    gps_lon: float | None
    location_name: str | None
    width: int
    height: int
    file_size: int
    media_type: str = "photo"
    duration: float | None = None
    thumb_sm_url: str | None = None
    thumb_md_url: str | None = None
    original_url: str | None = None
    indexed_at: datetime | None

    model_config = {"from_attributes": True}


class PhotoListResponse(BaseModel):
    items: list[PhotoOut]
    total: int
    page: int
    page_size: int


class ScanResponse(BaseModel):
    task_id: str


class ScanStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
