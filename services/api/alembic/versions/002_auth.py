"""Auth and user-management schema.

Revision ID: 002_auth
Revises: 001_initial
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002_auth"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="operator"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.String(512)),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", sa.String(64)),
        sa.Column("ip", sa.String(64)),
        sa.Column("details", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.add_column(
        "videos",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_videos_created_by_user_id", "videos", ["created_by_user_id"])

    op.add_column(
        "processing_jobs",
        sa.Column(
            "created_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
    )
    op.create_index("ix_processing_jobs_created_by_user_id", "processing_jobs", ["created_by_user_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_jobs_created_by_user_id", table_name="processing_jobs")
    op.drop_column("processing_jobs", "created_by_user_id")
    op.drop_index("ix_videos_created_by_user_id", table_name="videos")
    op.drop_column("videos", "created_by_user_id")
    op.drop_table("audit_logs")
    op.drop_table("sessions")
    op.drop_table("users")
