from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Investigation(Base):
    """Investigation findings, collected telemetry signals, and correlated traces."""

    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), default="InvestigationAgent", nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    telemetry_summary: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    correlated_traces: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="investigations")


class Diagnosis(Base):
    """Diagnosis hypothesis, structured chain of thought, and confidence score."""

    __tablename__ = "diagnoses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), default="DiagnosisAgent", nullable=False)
    root_cause_hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    chain_of_thought: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    risk_assessment: Mapped[str] = mapped_column(Text, default="", nullable=False)
    diagnosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="diagnoses")

    __table_args__ = (
        Index("ix_diagnoses_incident_confidence", "incident_id", "confidence_score"),
    )
