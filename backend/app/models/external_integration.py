from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExternalWebsiteIntegration(Base):
    """Persisted metadata for externally monitored website and service integrations."""

    __tablename__ = "external_website_integrations"
    __table_args__ = (
        Index("ix_external_website_integrations_name_unique", "name", unique=True),
        Index("ix_external_website_integrations_base_url_unique", "base_url", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    health_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    service_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    service_identifier: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    integration_method: Mapped[str] = mapped_column(String(30), default="http", nullable=False)
    api_key_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unverified", nullable=False, index=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
