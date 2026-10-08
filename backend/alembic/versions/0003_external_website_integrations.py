"""Add external website integration table.

Revision ID: 0003_external_integrations
Revises: 0002_postmortem_details
Create Date: 2026-10-06 20:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.types import JSON

revision: str = "0003_external_integrations"
down_revision: Union[str, None] = "0002_postmortem_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_website_integrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("health_url", sa.String(length=512), nullable=True),
        sa.Column("webhook_url", sa.String(length=512), nullable=True),
        sa.Column("service_name", sa.String(length=150), nullable=True),
        sa.Column("service_identifier", sa.String(length=150), nullable=True),
        sa.Column("integration_method", sa.String(length=30), nullable=False, server_default="http"),
        sa.Column("api_key_reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_response_time_ms", sa.Integer(), nullable=True),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("metadata", JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_external_website_integrations_name", "external_website_integrations", ["name"], unique=False)
    op.create_index("ix_external_website_integrations_service_name", "external_website_integrations", ["service_name"], unique=False)
    op.create_index("ix_external_website_integrations_status", "external_website_integrations", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_external_website_integrations_status", table_name="external_website_integrations")
    op.drop_index("ix_external_website_integrations_service_name", table_name="external_website_integrations")
    op.drop_index("ix_external_website_integrations_name", table_name="external_website_integrations")
    op.drop_table("external_website_integrations")
