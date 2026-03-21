import uuid
from datetime import datetime

from sqlalchemy import String, Integer, BigInteger, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class Photo(UUIDMixin, Base):
    __tablename__ = "photos"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    relative_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    taken_at: Mapped[datetime | None] = mapped_column(nullable=True)
    gps_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    media_type: Mapped[str] = mapped_column(String(16), nullable=False, default="photo")
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    thumb_sm: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumb_md: Mapped[str | None] = mapped_column(String(512), nullable=True)
    indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
