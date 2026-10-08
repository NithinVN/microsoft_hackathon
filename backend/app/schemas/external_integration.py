from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ExternalWebsiteIntegrationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    base_url: str = Field(..., min_length=8, max_length=512)
    health_url: Optional[str] = Field(default=None, max_length=512)
    webhook_url: Optional[str] = Field(default=None, max_length=512)
    service_name: Optional[str] = Field(default=None, max_length=150)
    service_identifier: Optional[str] = Field(default=None, max_length=150)
    integration_method: str = Field(default="http", max_length=30)
    api_key: Optional[str] = Field(default=None, description="Optional token used only for test/scan and never persisted.")


class ExternalWebsiteIntegrationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    base_url: Optional[str] = Field(default=None, min_length=8, max_length=512)
    health_url: Optional[str] = Field(default=None, max_length=512)
    webhook_url: Optional[str] = Field(default=None, max_length=512)
    service_name: Optional[str] = Field(default=None, max_length=150)
    service_identifier: Optional[str] = Field(default=None, max_length=150)
    status: Optional[str] = Field(default=None, max_length=30)
    metadata_json: Optional[Dict[str, Any]] = Field(default=None)


class ExternalWebsiteIntegrationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    base_url: str
    health_url: Optional[str] = None
    webhook_url: Optional[str] = None
    service_name: Optional[str] = None
    service_identifier: Optional[str] = None
    integration_method: str
    status: str
    last_checked_at: Optional[datetime] = None
    last_response_time_ms: Optional[int] = None
    last_status_code: Optional[int] = None
    last_error: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ExternalWebsiteConnectionTestResult(BaseModel):
    integration_id: int
    status: str
    reachable: bool
    http_status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    timeout_seconds: float
    endpoint: str
    health_status: Optional[str] = None
    health_payload: Optional[Dict[str, Any]] = None
    last_checked_at: datetime
    error: Optional[str] = None


class ExternalWebsiteFlaw(BaseModel):
    flaw_id: str
    title: str
    category: str
    severity: str
    confidence: float
    status: str
    description: str
    evidence: List[str]
    affected_endpoint: str
    observed_value: str
    expected_value: str
    impact: str
    likely_cause: str
    recommended_action: str


class ExternalWebsiteScanResult(BaseModel):
    integration_id: int
    service: str
    overall_status: str
    health_status: str
    api_status: str
    dependencies_status: str
    database_status: str
    http_status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    incident_id: Optional[str] = None
    detected_flaws: List[ExternalWebsiteFlaw] = Field(default_factory=list)
    evidence_summary: List[str] = Field(default_factory=list)
    last_checked_at: datetime
    raw_data: Dict[str, Any] = Field(default_factory=dict)


class ExternalWebsiteScanRequest(BaseModel):
    force_refresh: bool = False


class ExternalWebsiteConnectionTestRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional token used only for this specific test and not persisted.")
