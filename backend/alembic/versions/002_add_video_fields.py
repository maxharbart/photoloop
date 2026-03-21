"""Add video support fields

Revision ID: 002
Revises: 001
Create Date: 2026-03-21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("media_type", sa.String(16), nullable=False, server_default="photo"))
    op.add_column("photos", sa.Column("duration", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("photos", "duration")
    op.drop_column("photos", "media_type")
