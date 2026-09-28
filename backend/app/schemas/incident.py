from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field


class IncidentBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(default="")
    severity: str = Field(default="SEV-2", pattern="^SEV-[1-4]$")
    status: str = Field(default="DETECTED")
    source: str = Field(default="simulator")
    affected_service: str = Field(..., min_length=2, max_length=100)
    symptoms: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class IncidentCreate(IncidentBase):
    incident_id: str = Field(..., min_length=3, max_length=50)
    detected_at: Optional[datetime] = None


class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    severity: Optional[str] = Field(None, pattern="^SEV-[1-4]$")
    status: Optional[str] = None
    resolved_at: Optional[datetime] = None
    symptoms: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class IncidentEventCreate(BaseModel):
    event_type: str = Field(..., min_length=2, max_length=50)
    actor: str = Field(..., min_length=2, max_length=100)
    message: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None


class IncidentEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    event_type: str
    timestamp: datetime
    actor: str
    message: str
    payload: Dict[str, Any]


class InvestigationCreate(BaseModel):
    agent_name: str = Field(default="InvestigationAgent")
    findings: str = Field(..., min_length=1)
    telemetry_summary: Dict[str, Any] = Field(default_factory=dict)
    correlated_traces: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class InvestigationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    agent_name: str
    findings: str
    telemetry_summary: Dict[str, Any]
    correlated_traces: List[Dict[str, Any]]
    started_at: datetime
    completed_at: Optional[datetime] = None


class DiagnosisCreate(BaseModel):
    agent_name: str = Field(default="DiagnosisAgent")
    root_cause_hypothesis: str = Field(..., min_length=5)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    chain_of_thought: List[str] = Field(default_factory=list)
    risk_assessment: str = Field(default="")
    diagnosed_at: Optional[datetime] = None


class DiagnosisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    agent_name: str
    root_cause_hypothesis: str
    confidence_score: float
    chain_of_thought: List[str]
    risk_assessment: str
    diagnosed_at: datetime


class RemediationActionCreate(BaseModel):
    action_key: str = Field(..., min_length=2, max_length=50)
    title: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    command_template: str = Field(..., min_length=3)
    safety_level: str = Field(default="SAFE")
    historical_precedent: str = Field(default="UNTESTED")
    is_recommended: bool = Field(default=False)


class RemediationActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    action_key: str
    title: str
    description: str
    command_template: str
    safety_level: str
    historical_precedent: str
    is_recommended: bool
    created_at: datetime


class ActionExecutionCreate(BaseModel):
    remediation_action_id: int
    status: str = Field(default="PENDING_APPROVAL")
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    executed_at: Optional[datetime] = None
    execution_output: Optional[str] = None
    verification_status: Optional[str] = None


class ActionExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    remediation_action_id: int
    incident_id: int
    status: str
    approved_by: Optional[str] = None
    approval_notes: Optional[str] = None
    executed_at: Optional[datetime] = None
    execution_output: Optional[str] = None
    verification_status: Optional[str] = None


class EngineerFeedbackCreate(BaseModel):
    engineer_id: str = Field(..., min_length=2, max_length=100)
    rating: int = Field(..., ge=1, le=5)
    comments: str = Field(..., min_length=3)
    accuracy_evaluation: Optional[str] = None


class EngineerFeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    engineer_id: str
    rating: int
    comments: str
    accuracy_evaluation: Optional[str] = None
    submitted_at: datetime


class PostmortemCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    duration_minutes: int = Field(default=0, ge=0)
    root_cause: str = Field(..., min_length=5)
    trigger_event: str = Field(default="")
    corrective_actions: List[str] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    hindsight_retained: bool = Field(default=False)
    hindsight_memory_id: Optional[str] = None


class PostmortemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: int
    title: str
    duration_minutes: int
    root_cause: str
    trigger_event: str
    corrective_actions: List[str]
    timeline: List[Dict[str, Any]]
    hindsight_retained: bool
    hindsight_memory_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    incident_id: str
    title: str
    description: str
    severity: str
    status: str
    source: str
    affected_service: str
    symptoms: List[str] = Field(default_factory=list)
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)
    events: List[IncidentEventRead] = Field(default_factory=list)

    @computed_field
    @property
    def metadata(self) -> Dict[str, Any]:
        return self.metadata_json
