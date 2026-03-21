from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.routers.auth import hash_password, create_access_token
from app.schemas.auth import Token

router = APIRouter(prefix="/api/setup", tags=["setup"])


class SetupStatus(BaseModel):
    needs_setup: bool


class SetupRequest(BaseModel):
    username: str
    password: str
    project_name: str
    project_slug: str
    project_source_path: str


class SetupResponse(BaseModel):
    access_token: str
    project_slug: str


@router.get("/status", response_model=SetupStatus)
async def setup_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(User))
    count = result.scalar()
    return SetupStatus(needs_setup=count == 0)


@router.post("", response_model=SetupResponse, status_code=status.HTTP_201_CREATED)
async def run_setup(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count()).select_from(User))
    if result.scalar() > 0:
        raise HTTPException(status_code=403, detail="Setup already completed")

    if ".." in body.project_source_path or body.project_source_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid source_path")

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        is_superuser=True,
    )
    db.add(user)
    await db.flush()

    project = Project(
        slug=body.project_slug,
        name=body.project_name,
        source_path=body.project_source_path,
    )
    db.add(project)
    await db.flush()

    member = ProjectMember(project_id=project.id, user_id=user.id, role="owner")
    db.add(member)
    await db.commit()

    return SetupResponse(
        access_token=create_access_token(user.id),
        project_slug=project.slug,
    )
