from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AzureAlertEssentials(BaseModel):
    """Azure Monitor Common Alert Schema essentials block.
    
    Reference: https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    alert_id: str = Field(..., alias="alertId")
    alert_rule: str = Field(..., alias="alertRule")
    severity: str = Field(default="Sev2")
    signal_type: Optional[str] = Field(default=None, alias="signalType")
    monitor_condition: Literal["Fired", "Resolved"] = Field(default="Fired", alias="monitorCondition")
    monitoring_service: Optional[str] = Field(default=None, alias="monitoringService")
    alert_target_ids: List[str] = Field(default_factory=list, alias="alertTargetIDs")
    origin_alert_id: Optional[str] = Field(default=None, alias="originAlertId")
    fired_date_time: Optional[datetime] = Field(default=None, alias="firedDateTime")
    resolved_date_time: Optional[datetime] = Field(default=None, alias="resolvedDateTime")
    description: Optional[str] = Field(default="")
    essentials_version: Optional[str] = Field(default=None, alias="essentialsVersion")
    alert_context_version: Optional[str] = Field(default=None, alias="alertContextVersion")


class AzureCommonAlertData(BaseModel):
    """Payload data block inside Azure Monitor webhook notifications."""
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    # Common Alert Schema structure
    essentials: Optional[AzureAlertEssentials] = None
    alert_context: Optional[Dict[str, Any]] = Field(default=None, alias="alertContext")
    custom_properties: Optional[Dict[str, Any]] = Field(default=None, alias="customProperties")

    # Classic/Legacy or non-common schema fallback fields
    status: Optional[str] = None  # e.g. "Activated", "Deactivated", "Fired", "Resolved"
    context: Optional[Dict[str, Any]] = None
    properties: Optional[Dict[str, Any]] = None


class AzureMonitorWebhookPayload(BaseModel):
    """Normalized ingestion model for Azure Monitor Webhook alerts.
    
    Supports:
    1. Azure Monitor Common Alert Schema (Standard & recommended)
    2. Classic / legacy Azure metric & log alert schemas
    """
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    schema_id: Optional[str] = Field(default="azureMonitorCommonAlertSchema", alias="schemaId")
    data: AzureCommonAlertData

    @model_validator(mode="after")
    def validate_alert_payload(self) -> AzureMonitorWebhookPayload:
        data = self.data
        if data.essentials is None and data.context is None and not (data.status and (data.properties or data.custom_properties)):
            raise ValueError(
                "Invalid Azure Monitor payload: missing both 'essentials' (Common Alert Schema) and 'context' (Classic Schema)."
            )
        return self

    def is_resolved(self) -> bool:
        if self.data.essentials:
            return self.data.essentials.monitor_condition.strip().lower() == "resolved"
        if self.data.status:
            return self.data.status.strip().lower() in {"deactivated", "resolved"}
        return False

    def is_firing(self) -> bool:
        return not self.is_resolved()

    def get_fingerprint(self) -> str:
        """Derive a deterministic, idempotent alert fingerprint."""
        if self.data.essentials:
            essentials = self.data.essentials
            # Prefer originAlertId if present, otherwise alertId
            base_id = essentials.origin_alert_id or essentials.alert_id
            if base_id and len(base_id) >= 8:
                return hashlib.sha256(base_id.encode("utf-8")).hexdigest()[:32]
            # Fallback to rule + first target
            target = essentials.alert_target_ids[0] if essentials.alert_target_ids else "no-target"
            raw = f"azure:{essentials.alert_rule}:{target}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

        # Classic fallback
        context = self.data.context or {}
        alert_id = context.get("id") or context.get("name") or "classic-azure-alert"
        return hashlib.sha256(str(alert_id).encode("utf-8")).hexdigest()[:32]

    def get_alert_name(self) -> str:
        if self.data.essentials and self.data.essentials.alert_rule:
            return self.data.essentials.alert_rule.strip()
        if self.data.context:
            name = self.data.context.get("name") or self.data.context.get("alertRule")
            if name:
                return str(name).strip()
        return "AzureMonitorAlert"

    def get_service_name(self, default_service: str = "azure-service") -> str:
        """Extract service name from customProperties, tags, or resource IDs."""
        props = self.data.custom_properties or self.data.properties or {}
        for key in ("service", "app", "application", "service_name", "component", "job"):
            val = props.get(key)
            if val and str(val).strip():
                return str(val).strip()[:100]

        # Check alertTargetIDs (e.g., /subscriptions/.../providers/Microsoft.Compute/virtualMachines/payment-api)
        if self.data.essentials and self.data.essentials.alert_target_ids:
            target = self.data.essentials.alert_target_ids[0]
            parts = [p for p in target.split("/") if p]
            if parts:
                return parts[-1][:100]

        # Check classic context resourceName
        if self.data.context:
            res_name = self.data.context.get("resourceName")
            if res_name:
                return str(res_name).strip()[:100]

        return default_service

    def get_severity(self) -> str:
        if self.data.essentials:
            return self.data.essentials.severity
        if self.data.context:
            sev = self.data.context.get("severity")
            if sev is not None:
                return str(sev)
        return "Sev2"

    def get_description(self) -> str:
        if self.data.essentials and self.data.essentials.description:
            return self.data.essentials.description.strip()
        if self.data.context:
            desc = self.data.context.get("description")
            if desc:
                return str(desc).strip()
        return self.get_alert_name()

    def get_symptoms(self) -> List[str]:
        symptoms: List[str] = []
        desc = self.get_description()
        if desc and desc != self.get_alert_name():
            symptoms.append(desc)

        # Extract metric condition symptoms if present
        context = self.data.alert_context or self.data.context or {}
        condition = context.get("condition") or {}
        all_of = condition.get("allOf") or []
        for crit in all_of:
            m_name = crit.get("metricName")
            op = crit.get("operator", ">")
            thresh = crit.get("threshold")
            val = crit.get("metricValue")
            if m_name and thresh is not None:
                line = f"{m_name} {op} {thresh}"
                if val is not None:
                    line += f" (observed: {val})"
                symptoms.append(line)

        # Single condition format (Classic)
        if not all_of and condition.get("metricName"):
            m_name = condition.get("metricName")
            op = condition.get("operator", ">")
            thresh = condition.get("threshold")
            val = condition.get("metricValue")
            line = f"{m_name} {op} {thresh}"
            if val is not None:
                line += f" (observed: {val})"
            symptoms.append(line)

        if not symptoms:
            symptoms.append(self.get_alert_name())
        return list(dict.fromkeys(symptoms))

    def get_telemetry_summary(self) -> Dict[str, Any]:
        summary: Dict[str, Any] = {}
        context = self.data.alert_context or self.data.context or {}
        if "condition" in context:
            summary["condition"] = context["condition"]
        if "conditionType" in context:
            summary["condition_type"] = context["conditionType"]
        if self.data.essentials:
            summary["signal_type"] = self.data.essentials.signal_type
            summary["monitoring_service"] = self.data.essentials.monitoring_service
            summary["alert_target_ids"] = self.data.essentials.alert_target_ids
        return summary

    def get_fired_date_time(self) -> datetime:
        if self.data.essentials and self.data.essentials.fired_date_time:
            return self.data.essentials.fired_date_time
        if self.data.context and self.data.context.get("timestamp"):
            try:
                return datetime.fromisoformat(self.data.context["timestamp"].replace("Z", "+00:00"))
            except Exception:
                pass
        return utcnow()

    def get_resolved_date_time(self) -> datetime:
        if self.data.essentials and self.data.essentials.resolved_date_time:
            return self.data.essentials.resolved_date_time
        return utcnow()

    def get_raw_payload(self) -> Dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json")
