import uuid
from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    slug: str
    name: str
    source_path: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    source_path: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    source_path: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberAdd(BaseModel):
    user_id: uuid.UUID
    role: str = "viewer"


class MemberOut(BaseModel):
    user_id: uuid.UUID
    role: str

    model_config = {"from_attributes": True}
