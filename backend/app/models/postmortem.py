from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
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


class EngineerFeedback(Base):
    """Human engineer evaluation and rating of agent diagnostic & remediation efficacy."""

    __tablename__ = "engineer_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), index=True, nullable=False)
    engineer_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # 1 to 5 stars
    comments: Mapped[str] = mapped_column(Text, nullable=False)
    accuracy_evaluation: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="feedbacks")

    __table_args__ = (
        Index("ix_feedbacks_incident_rating", "incident_id", "rating"),
    )


class Postmortem(Base):
    """Incident postmortem report and Hindsight organizational memory retain record."""

    __tablename__ = "postmortems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_event: Mapped[str] = mapped_column(Text, default="", nullable=False)
    corrective_actions: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    timeline: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    hindsight_retained: Mapped[bool] = mapped_column(Boolean, default=False, index=True, nullable=False)
    hindsight_memory_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    incident: Mapped["Incident"] = relationship("Incident", back_populates="postmortem")
