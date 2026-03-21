import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.project import Project, ProjectMember
from app.models.user import User
from app.routers.auth import get_current_user, require_superuser
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectOut, MemberAdd, MemberOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _validate_source_path(source_path: str) -> None:
    if ".." in source_path or source_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid source_path")


async def _get_project_by_slug(slug: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _require_member(project: Project, user: User, db: AsyncSession) -> ProjectMember | None:
    if user.is_superuser:
        return None
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=403, detail="Not a project member")
    return member


async def _require_owner(project: Project, user: User, db: AsyncSession) -> None:
    if user.is_superuser:
        return
    member = await _require_member(project, user, db)
    if member is None or member.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")


@router.get("", response_model=list[ProjectOut])
async def list_projects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_superuser:
        result = await db.execute(select(Project))
    else:
        result = await db.execute(
            select(Project)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(ProjectMember.user_id == current_user.id)
        )
    return result.scalars().all()


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(
    body: ProjectCreate,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
):
    _validate_source_path(body.source_path)
    project = Project(**body.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{slug}", response_model=ProjectOut)
async def get_project(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_member(project, current_user, db)
    return project


@router.put("/{slug}", response_model=ProjectOut)
async def update_project(
    slug: str,
    body: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_owner(project, current_user, db)
    update_data = body.model_dump(exclude_unset=True)
    if "source_path" in update_data:
        _validate_source_path(update_data["source_path"])
    for key, value in update_data.items():
        setattr(project, key, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.post("/{slug}/members", response_model=MemberOut, status_code=201)
async def add_member(
    slug: str,
    body: MemberAdd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_owner(project, current_user, db)
    member = ProjectMember(project_id=project.id, user_id=body.user_id, role=body.role)
    db.add(member)
    await db.commit()
    return member


@router.delete("/{slug}/members/{user_id}", status_code=204)
async def remove_member(
    slug: str,
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project_by_slug(slug, db)
    await _require_owner(project, current_user, db)
    result = await db.execute(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    await db.delete(member)
    await db.commit()
