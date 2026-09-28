from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RemediationAction(Base):
    """Candidate pre-approved remediation actions evaluated by Remediation Agent."""

    __tablename__ = "remediation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    action_key: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    command_template: Mapped[str] = mapped_column(Text, nullable=False)  # Vetted parameterized routine - NOT arbitrary shell
    safety_level: Mapped[str] = mapped_column(String(20), default="SAFE", index=True, nullable=False)
    historical_precedent: Mapped[str] = mapped_column(String(30), default="UNTESTED", nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="remediations")
    executions: Mapped[List["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="remediation_action", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_remediation_incident_rec", "incident_id", "is_recommended"),
    )


class ActionExecution(Base):
    """Execution audit trail, human approval records, and verification status."""

    __tablename__ = "action_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    remediation_action_id: Mapped[int] = mapped_column(Integer, ForeignKey("remediation_actions.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_APPROVAL", index=True, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    approval_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    remediation_action: Mapped["RemediationAction"] = relationship("RemediationAction", back_populates="executions")
    incident: Mapped["Incident"] = relationship("Incident", back_populates="executions")

    __table_args__ = (
        Index("ix_executions_incident_status", "incident_id", "status"),
    )
