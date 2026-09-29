from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AlertmanagerAlert(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    status: Optional[Literal["firing", "resolved"]] = None
    labels: Dict[str, str] = Field(min_length=1)
    annotations: Dict[str, str] = Field(default_factory=dict)
    starts_at: datetime = Field(default_factory=utcnow, alias="startsAt")
    ends_at: Optional[datetime] = Field(default=None, alias="endsAt")
    generator_url: Optional[str] = Field(default=None, alias="generatorURL")
    fingerprint: Optional[str] = Field(default=None, min_length=3, max_length=100)
    value: Optional[str] = None

    @field_validator("labels")
    @classmethod
    def validate_alert_name(cls, value: Dict[str, str]) -> Dict[str, str]:
        if not value.get("alertname", "").strip():
            raise ValueError("labels.alertname is required")
        return value


class AlertmanagerWebhookPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    receiver: Optional[str] = None
    status: Literal["firing", "resolved"]
    alerts: List[AlertmanagerAlert] = Field(min_length=1, max_length=100)
    group_labels: Dict[str, str] = Field(default_factory=dict, alias="groupLabels")
    common_labels: Dict[str, str] = Field(default_factory=dict, alias="commonLabels")
    common_annotations: Dict[str, str] = Field(default_factory=dict, alias="commonAnnotations")
    external_url: Optional[str] = Field(default=None, alias="externalURL")
    version: Optional[str] = None
    group_key: Optional[str] = Field(default=None, alias="groupKey")
    truncated_alerts: int = Field(default=0, alias="truncatedAlerts", ge=0)
