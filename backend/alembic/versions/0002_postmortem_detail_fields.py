"""Add postmortem detail fields missing from the initial migration.

Revision ID: 0002_postmortem_details
Revises: 0001_initial
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import JSON

revision: str = "0002_postmortem_details"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = [
        ("incident_summary", sa.Text(), ""),
        ("impact", sa.Text(), ""),
        ("detection", sa.Text(), ""),
        ("what_happened", sa.Text(), ""),
        ("what_worked", JSON(), "[]"),
        ("what_failed", JSON(), "[]"),
        ("why_it_failed", sa.Text(), ""),
        ("contributing_factors", sa.Text(), ""),
        ("actual_outcome", sa.Text(), ""),
        ("final_resolution", sa.Text(), ""),
        ("engineer_corrections", JSON(), "[]"),
        ("engineer_feedback", sa.Text(), ""),
        ("lessons_learned", JSON(), "[]"),
        ("future_prevention", sa.Text(), ""),
    ]
    for name, column_type, default in columns:
        op.add_column(
            "postmortems",
            sa.Column(name, column_type, nullable=False, server_default=default),
        )


def downgrade() -> None:
    for name in [
        "future_prevention",
        "lessons_learned",
        "engineer_feedback",
        "engineer_corrections",
        "final_resolution",
        "actual_outcome",
        "contributing_factors",
        "why_it_failed",
        "what_failed",
        "what_worked",
        "what_happened",
        "detection",
        "impact",
        "incident_summary",
    ]:
        op.drop_column("postmortems", name)
