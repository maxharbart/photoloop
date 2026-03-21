"""Initial migration

Revision ID: 001
Revises:
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("is_superuser", sa.Boolean, server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), unique=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("source_path", sa.String(1024), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "project_members",
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
    )

    op.create_table(
        "photos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relative_path", sa.String(2048), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gps_lat", sa.Float, nullable=True),
        sa.Column("gps_lon", sa.Float, nullable=True),
        sa.Column("location_name", sa.String(512), nullable=True),
        sa.Column("width", sa.Integer, nullable=False, server_default="0"),
        sa.Column("height", sa.Integer, nullable=False, server_default="0"),
        sa.Column("file_size", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("thumb_sm", sa.String(512), nullable=True),
        sa.Column("thumb_md", sa.String(512), nullable=True),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "albums",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("cover_photo_id", UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "album_photos",
        sa.Column("album_id", UUID(as_uuid=True), sa.ForeignKey("albums.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("photo_id", UUID(as_uuid=True), sa.ForeignKey("photos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sort_order", sa.Integer, server_default="0"),
    )

    # Useful indexes
    op.create_index("ix_photos_project_taken_at", "photos", ["project_id", "taken_at"])
    op.create_index("ix_photos_project_relative_path", "photos", ["project_id", "relative_path"])


def downgrade() -> None:
    op.drop_index("ix_photos_project_relative_path")
    op.drop_index("ix_photos_project_taken_at")
    op.drop_table("album_photos")
    op.drop_table("albums")
    op.drop_table("photos")
    op.drop_table("project_members")
    op.drop_table("projects")
    op.drop_table("users")
