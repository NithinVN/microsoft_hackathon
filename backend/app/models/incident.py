from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    DateTime,
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


class Service(Base):
    """Catalog of operational services and dependencies."""

    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    owner_team: Mapped[str] = mapped_column(String(100), default="sre", nullable=False)
    repository_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    health_status: Mapped[str] = mapped_column(String(20), default="HEALTHY", nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    deployments: Mapped[List["Deployment"]] = relationship(
        "Deployment", back_populates="service", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_services_tier_health", "tier", "health_status"),
    )


class Deployment(Base):
    """Service deployment history for change correlation during investigation."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id", ondelete="CASCADE"), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    environment: Mapped[str] = mapped_column(String(50), default="production", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False)
    deployed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    commit_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    service: Mapped["Service"] = relationship("Service", back_populates="deployments")

    __table_args__ = (
        Index("ix_deployments_service_env_date", "service_id", "environment", "deployed_at"),
    )


class Alert(Base):
    """Raw alert event received from telemetry, Prometheus, or simulator."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    incident_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="SET NULL"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="simulator", nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="firing", index=True, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    incident: Mapped[Optional["Incident"]] = relationship("Incident", back_populates="alerts")


class Incident(Base):
    """Primary operational incident entity managed by IncidentMind state machine."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="SEV-2", index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DETECTED", index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), default="simulator", nullable=False)
    affected_service: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    symptoms: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    events: Mapped[List["IncidentEvent"]] = relationship(
        "IncidentEvent", back_populates="incident", cascade="all, delete-orphan", order_by="IncidentEvent.timestamp.asc()"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="incident"
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", back_populates="incident", cascade="all, delete-orphan"
    )
    diagnoses: Mapped[List["Diagnosis"]] = relationship(
        "Diagnosis", back_populates="incident", cascade="all, delete-orphan"
    )
    remediations: Mapped[List["RemediationAction"]] = relationship(
        "RemediationAction", back_populates="incident", cascade="all, delete-orphan"
    )
    executions: Mapped[List["ActionExecution"]] = relationship(
        "ActionExecution", back_populates="incident", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[List["EngineerFeedback"]] = relationship(
        "EngineerFeedback", back_populates="incident", cascade="all, delete-orphan"
    )
    postmortem: Mapped[Optional["Postmortem"]] = relationship(
        "Postmortem", back_populates="incident", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        Index("ix_incidents_status_severity", "status", "severity"),
        Index("ix_incidents_service_status", "affected_service", "status"),
    )


class IncidentEvent(Base):
    """Chronological event timeline tracking agent executions and human decisions."""

    __tablename__ = "incident_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="events")

    __table_args__ = (
        Index("ix_incident_events_incident_time", "incident_id", "timestamp"),
    )
