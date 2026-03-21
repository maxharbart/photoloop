import uuid
from datetime import datetime

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    is_superuser: bool = False


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    is_superuser: bool
    created_at: datetime

    model_config = {"from_attributes": True}
