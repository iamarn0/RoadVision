"""West Bengal districts, appointments, and video jurisdiction.

Revision ID: 003_districts
Revises: 002_auth
Create Date: 2026-09-22
"""

from typing import Sequence, Union
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from packages.db.districts import WEST_BENGAL_DISTRICTS, district_slug

revision: str = "003_districts"
down_revision: Union[str, None] = "002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "districts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
    )
    op.create_index("ix_districts_name", "districts", ["name"], unique=True)
    op.create_index("ix_districts_slug", "districts", ["slug"], unique=True)

    op.create_table(
        "user_districts",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "district_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("districts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.add_column(
        "videos",
        sa.Column(
            "district_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("districts.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_videos_district_id", "videos", ["district_id"])

    districts = sa.table(
        "districts",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
    )
    op.bulk_insert(
        districts,
        [{"id": uuid4(), "name": name, "slug": district_slug(name)} for name in WEST_BENGAL_DISTRICTS],
    )


def downgrade() -> None:
    op.drop_index("ix_videos_district_id", table_name="videos")
    op.drop_column("videos", "district_id")
    op.drop_table("user_districts")
    op.drop_index("ix_districts_slug", table_name="districts")
    op.drop_index("ix_districts_name", table_name="districts")
    op.drop_table("districts")
