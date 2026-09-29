from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.models.incident import Alert
from backend.app.orchestration.incident_orchestrator import IncidentOrchestrator
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.alertmanager import AlertmanagerAlert, AlertmanagerWebhookPayload
from backend.app.schemas.azure_monitor import AzureMonitorWebhookPayload
from backend.app.schemas.incident import IncidentCreate
from backend.app.services.incident_intake import IncidentIntakeService, normalize_severity

router = APIRouter()


def _fingerprint(alert: AlertmanagerAlert) -> str:
    if alert.fingerprint:
        return alert.fingerprint
    serialized = json.dumps(alert.labels, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _alert_payload(alert: AlertmanagerAlert, envelope: AlertmanagerWebhookPayload) -> Dict[str, Any]:
    return {
        "labels": alert.labels,
        "annotations": alert.annotations,
        "startsAt": alert.starts_at.isoformat(),
        "endsAt": alert.ends_at.isoformat() if alert.ends_at else None,
        "fingerprint": _fingerprint(alert),
        "generatorURL": alert.generator_url,
        "value": alert.value,
        "receiver": envelope.receiver,
        "groupKey": envelope.group_key,
        "groupLabels": envelope.group_labels,
        "commonLabels": envelope.common_labels,
        "commonAnnotations": envelope.common_annotations,
        "externalURL": envelope.external_url,
    }


def _incident_id(fingerprint: str, starts_at: datetime) -> str:
    key = f"{fingerprint}:{starts_at.isoformat()}"
    suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12].upper()
    return f"INC-AM-{suffix}"


def _service_name(labels: Dict[str, str]) -> str:
    return (
        (labels.get("service") or "").strip()
        or (labels.get("application") or "").strip()
        or (labels.get("app") or "").strip()
        or (labels.get("job") or "").strip()
        or "unknown-service"
    )[:100]


def _resolved_at(alert: AlertmanagerAlert) -> datetime:
    timestamp = alert.ends_at
    if timestamp is None or timestamp.year <= 1 or timestamp < alert.starts_at:
        return datetime.now(timezone.utc)
    return timestamp


async def _find_alert(session: AsyncSession, fingerprint: str, *, active_only: bool) -> Optional[Alert]:
    statement = select(Alert).where(Alert.alert_id == fingerprint)
    if active_only:
        statement = statement.where(Alert.status == "firing")
    statement = statement.order_by(Alert.triggered_at.desc()).limit(1)
    return (await session.execute(statement)).scalar_one_or_none()


def verify_alertmanager_webhook_secret(
    x_alertmanager_webhook_secret: Optional[str] = Header(None, alias="X-Alertmanager-Webhook-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> None:
    expected_secret = (settings.ALERTMANAGER_WEBHOOK_SECRET or "").strip()
    if not expected_secret:
        if settings.APP_ENV.lower() not in {"development", "test"}:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Alertmanager webhook authentication is not configured.")
        return

    provided_secret = (x_alertmanager_webhook_secret or "").strip()
    if not provided_secret and authorization:
        scheme, separator, credentials = authorization.partition(" ")
        if separator and scheme.lower() == "bearer":
            provided_secret = credentials.strip()

    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing Alertmanager webhook credentials.")


@router.post("/alertmanager", status_code=status.HTTP_200_OK)
async def receive_alertmanager_webhook(
    payload: AlertmanagerWebhookPayload,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_alertmanager_webhook_secret),
) -> Dict[str, Any]:
    """Normalize Alertmanager notifications into the shared incident intake pipeline."""
    intake = IncidentIntakeService(db)
    repository = IncidentRepository(db)
    results: List[Dict[str, Any]] = []
    created = 0
    resolved = 0
    ignored = 0

    try:
        for alert_data in payload.alerts:
            alert_status = alert_data.status or payload.status
            fingerprint = _fingerprint(alert_data)
            raw_payload = _alert_payload(alert_data, payload)
            if alert_status == "resolved":
                existing_alert = await _find_alert(db, fingerprint, active_only=True)
                if existing_alert is None:
                    latest_alert = await _find_alert(db, fingerprint, active_only=False)
                    if latest_alert is not None and latest_alert.status == "resolved":
                        incident_id = None
                        if latest_alert.incident_id is not None:
                            incident = await repository.get_incident_by_id(latest_alert.incident_id)
                            incident_id = incident.incident_id if incident else None
                        ignored += 1
                        results.append({"fingerprint": fingerprint, "status": "already_resolved", "incident_id": incident_id})
                        continue

                    resolved_at = _resolved_at(alert_data)
                    db.add(Alert(
                        alert_id=fingerprint,
                        name=alert_data.labels["alertname"],
                        source="alertmanager",
                        severity=alert_data.labels.get("severity", "warning"),
                        status="resolved",
                        payload=raw_payload,
                        triggered_at=alert_data.starts_at,
                        resolved_at=resolved_at,
                    ))
                    await db.commit()
                    ignored += 1
                    results.append({"fingerprint": fingerprint, "status": "unmatched_resolved", "incident_id": None})
                    continue

                resolved_at = _resolved_at(alert_data)
                incident = await intake.resolve_alert(existing_alert, resolved_at, raw_payload)
                resolved += 1
                results.append({
                    "fingerprint": fingerprint,
                    "status": "resolved",
                    "incident_id": incident.incident_id if incident else None,
                })
                continue

            existing_alert = await _find_alert(db, fingerprint, active_only=True)
            if existing_alert is not None:
                existing_alert.payload = raw_payload
                existing_alert.severity = alert_data.labels.get("severity", existing_alert.severity)
                await db.commit()
                incident_id = None
                if existing_alert.incident_id is not None:
                    incident = await repository.get_incident_by_id(existing_alert.incident_id)
                    incident_id = incident.incident_id if incident else None
                ignored += 1
                results.append({"fingerprint": fingerprint, "status": "already_firing", "incident_id": incident_id})
                continue

            alert_name = alert_data.labels["alertname"]
            service = _service_name(alert_data.labels)
            summary = alert_data.annotations.get("summary") or alert_name
            description = alert_data.annotations.get("description") or summary
            symptoms = [value for value in (summary, description) if value]
            severity = normalize_severity(alert_data.labels.get("severity"), "SEV-2")
            detected_at = alert_data.starts_at
            incident_create = IncidentCreate(
                incident_id=_incident_id(fingerprint, detected_at),
                title=f"[{service}] {summary}"[:255],
                description=description,
                severity=severity,
                status="DETECTED",
                source="alertmanager",
                affected_service=service,
                detected_at=detected_at,
                symptoms=list(dict.fromkeys(symptoms)),
                metadata={
                    "alertmanager": raw_payload,
                    "alert_labels": alert_data.labels,
                    "alert_annotations": alert_data.annotations,
                    "fingerprint": fingerprint,
                    "generator_url": alert_data.generator_url,
                    "alert_value": alert_data.value,
                },
            )
            alert, incident = await intake.create_from_alert(
                incident_data=incident_create,
                alert_data={
                    "alert_id": fingerprint,
                    "name": alert_name,
                    "source": "alertmanager",
                    "severity": alert_data.labels.get("severity", "warning"),
                    "status": "firing",
                    "payload": raw_payload,
                    "triggered_at": detected_at,
                },
                findings=f"Alertmanager firing alert {alert_name}: {description}",
                telemetry_summary={"labels": alert_data.labels, "annotations": alert_data.annotations, "value": alert_data.value},
                pipeline_payload={"source": "alertmanager", "fingerprint": fingerprint, "severity": severity},
            )
            created += 1
            results.append({"fingerprint": fingerprint, "status": "created", "incident_id": incident.incident_id, "alert_id": alert.alert_id})

    except Exception as exc:
        await db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Alertmanager notification could not be processed.",
        ) from exc

    return {
        "status": "accepted",
        "received": len(payload.alerts),
        "created": created,
        "resolved": resolved,
        "ignored": ignored,
        "results": results,
    }


def _azure_incident_id(fingerprint: str, starts_at: datetime) -> str:
    key = f"{fingerprint}:{starts_at.isoformat()}"
    suffix = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12].upper()
    return f"INC-AZ-{suffix}"


def verify_azure_webhook_secret(
    request: Request,
    code: Optional[str] = Query(None, description="Azure webhook secret token via query parameter (?code=...)"),
    x_azure_webhook_secret: Optional[str] = Header(None, alias="X-Azure-Webhook-Secret"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
) -> None:
    """Validate optional Azure Monitor Action Group webhook secret / authorization token."""
    expected_secret = (settings.AZURE_WEBHOOK_SECRET or "").strip()
    if not expected_secret:
        if settings.APP_ENV.lower() not in {"development", "test"}:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Azure webhook authentication is not configured.")
        return

    provided_secret = code or request.query_params.get("token") or request.query_params.get("secret")
    if not provided_secret and x_azure_webhook_secret:
        provided_secret = x_azure_webhook_secret.strip()
    if not provided_secret and authorization:
        parts = authorization.strip().split(" ")
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_secret = parts[1].strip()
        elif len(parts) == 1:
            provided_secret = parts[0].strip()

    if not provided_secret or not hmac.compare_digest(provided_secret, expected_secret):
        logger.warning(
            "Unauthorized Azure Monitor webhook attempt: invalid or missing secret token",
            extra={"path": str(request.url.path), "has_provided_secret": bool(provided_secret)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Azure webhook authentication credentials.",
        )


@router.post("/azure-monitor", status_code=status.HTTP_200_OK)
async def receive_azure_monitor_webhook(
    payload: AzureMonitorWebhookPayload,
    db: AsyncSession = Depends(get_db),
    _auth: None = Depends(verify_azure_webhook_secret),
    orchestrate: Optional[bool] = Query(
        None,
        description="Optionally trigger synchronous Incident Orchestrator execution",
    ),
) -> Dict[str, Any]:
    """Ingest, validate, and normalize Azure Monitor alerts into the shared incident pipeline.
    
    Accepts both Azure Monitor Common Alert Schema and classic alerts, normalizes them into
    the internal Incident schema, and hands off to the Incident Intake Service and Orchestrator.
    """
    intake = IncidentIntakeService(db)
    repository = IncidentRepository(db)

    fingerprint = payload.get_fingerprint()
    alert_name = payload.get_alert_name()
    service = payload.get_service_name(default_service=settings.AZURE_DEFAULT_SERVICE)
    raw_severity = payload.get_severity()
    severity = normalize_severity(raw_severity, default_sev="SEV-2")
    description = payload.get_description()
    symptoms = payload.get_symptoms()
    telemetry = payload.get_telemetry_summary()
    raw_payload = payload.get_raw_payload()
    is_resolved = payload.is_resolved()

    logger.info(
        "Azure Monitor alert webhook received: rule='%s', service='%s', severity='%s' (raw='%s'), condition='%s', fingerprint='%s'",
        alert_name,
        service,
        severity,
        raw_severity,
        "Resolved" if is_resolved else "Fired",
        fingerprint,
    )

    try:
        if is_resolved:
            existing_alert = await _find_alert(db, fingerprint, active_only=True)
            if existing_alert is None:
                latest_alert = await _find_alert(db, fingerprint, active_only=False)
                if latest_alert is not None and latest_alert.status == "resolved":
                    incident_id = None
                    if latest_alert.incident_id is not None:
                        incident = await repository.get_incident_by_id(latest_alert.incident_id)
                        incident_id = incident.incident_id if incident else None
                    logger.info("Azure Monitor alert '%s' was already resolved; skipping", alert_name)
                    return {
                        "status": "accepted",
                        "action": "already_resolved",
                        "fingerprint": fingerprint,
                        "incident_id": incident_id,
                        "service": service,
                        "created": 0,
                        "resolved": 0,
                        "ignored": 1,
                        "results": [{"fingerprint": fingerprint, "status": "already_resolved", "incident_id": incident_id}],
                    }

                resolved_at = payload.get_resolved_date_time()
                db.add(Alert(
                    alert_id=fingerprint,
                    name=alert_name,
                    source="azure-monitor",
                    severity=raw_severity,
                    status="resolved",
                    payload=raw_payload,
                    triggered_at=payload.get_fired_date_time(),
                    resolved_at=resolved_at,
                ))
                await db.commit()
                logger.info("Unmatched Azure Monitor resolved alert recorded for fingerprint '%s'", fingerprint)
                return {
                    "status": "accepted",
                    "action": "unmatched_resolved",
                    "fingerprint": fingerprint,
                    "incident_id": None,
                    "service": service,
                    "created": 0,
                    "resolved": 0,
                    "ignored": 1,
                    "results": [{"fingerprint": fingerprint, "status": "unmatched_resolved", "incident_id": None}],
                }

            resolved_at = payload.get_resolved_date_time()
            incident = await intake.resolve_alert(existing_alert, resolved_at, raw_payload)
            logger.info("Resolved incident '%s' from Azure Monitor resolution notification", incident.incident_id if incident else "none")
            return {
                "status": "accepted",
                "action": "resolved",
                "fingerprint": fingerprint,
                "incident_id": incident.incident_id if incident else None,
                "alert_id": existing_alert.alert_id,
                "service": service,
                "created": 0,
                "resolved": 1,
                "ignored": 0,
                "results": [{
                    "fingerprint": fingerprint,
                    "status": "resolved",
                    "incident_id": incident.incident_id if incident else None,
                }],
            }

        # Handling firing alert
        existing_alert = await _find_alert(db, fingerprint, active_only=True)
        if existing_alert is not None:
            existing_alert.payload = raw_payload
            existing_alert.severity = raw_severity
            await db.commit()
            incident_id = None
            if existing_alert.incident_id is not None:
                incident = await repository.get_incident_by_id(existing_alert.incident_id)
                incident_id = incident.incident_id if incident else None
            logger.info("Azure Monitor alert '%s' already firing; updated existing alert payload", alert_name)
            return {
                "status": "accepted",
                "action": "already_firing",
                "fingerprint": fingerprint,
                "incident_id": incident_id,
                "service": service,
                "created": 0,
                "resolved": 0,
                "ignored": 1,
                "results": [{"fingerprint": fingerprint, "status": "already_firing", "incident_id": incident_id}],
            }

        detected_at = payload.get_fired_date_time()
        incident_id = _azure_incident_id(fingerprint, detected_at)

        summary_title = f"[{service}] {alert_name}"
        if description and description != alert_name:
            summary_title = f"[{service}] {alert_name}: {description}"
        summary_title = summary_title[:255]

        incident_create = IncidentCreate(
            incident_id=incident_id,
            title=summary_title,
            description=description or alert_name,
            severity=severity,
            status="DETECTED",
            source="azure-monitor",
            affected_service=service,
            detected_at=detected_at,
            symptoms=symptoms,
            metadata={
                "azure_monitor": raw_payload,
                "schema_id": payload.schema_id,
                "fingerprint": fingerprint,
                "alert_rule": alert_name,
                "raw_severity": raw_severity,
                "telemetry": telemetry,
                "target_ids": payload.data.essentials.alert_target_ids if payload.data.essentials else [],
                "custom_properties": payload.data.custom_properties or payload.data.properties or {},
            },
        )

        alert, incident = await intake.create_from_alert(
            incident_data=incident_create,
            alert_data={
                "alert_id": fingerprint,
                "name": alert_name,
                "source": "azure-monitor",
                "severity": raw_severity,
                "status": "firing",
                "payload": raw_payload,
                "triggered_at": detected_at,
            },
            findings=f"Azure Monitor alert '{alert_name}' triggered on service '{service}': {description}",
            telemetry_summary=telemetry,
            pipeline_payload={
                "source": "azure-monitor",
                "fingerprint": fingerprint,
                "severity": severity,
                "schema_id": payload.schema_id,
            },
        )

        logger.info(
            "Created normalized incident '%s' from Azure Monitor alert '%s' on '%s' with severity %s",
            incident.incident_id,
            alert_name,
            service,
            severity,
        )

        orchestrator_status = "pipeline_initialized"
        orchestrator_step = "START"
        should_orchestrate = orchestrate if orchestrate is not None else settings.AZURE_AUTO_ORCHESTRATE

        if should_orchestrate:
            logger.info("Executing Incident Orchestrator workflow for '%s'", incident.incident_id)
            try:
                orchestrator = IncidentOrchestrator()
                orch_state = orchestrator.run(incident.incident_id)
                orchestrator_status = orch_state.status
                orchestrator_step = orch_state.current_step
                logger.info(
                    "Incident Orchestrator finished for '%s': status=%s, step=%s",
                    incident.incident_id,
                    orch_state.status,
                    orch_state.current_step,
                )
            except Exception as orch_exc:
                logger.error("Incident Orchestrator failed while processing an Azure alert (error_type=%s)", type(orch_exc).__name__)
                orchestrator_status = "orchestrator_failed"

        return {
            "status": "accepted",
            "action": "created",
            "fingerprint": fingerprint,
            "incident_id": incident.incident_id,
            "alert_id": alert.alert_id,
            "service": service,
            "severity": severity,
            "orchestrator_status": orchestrator_status,
            "orchestrator_step": orchestrator_step,
            "created": 1,
            "resolved": 0,
            "ignored": 0,
            "results": [
                {
                    "fingerprint": fingerprint,
                    "status": "created",
                    "incident_id": incident.incident_id,
                    "alert_id": alert.alert_id,
                    "orchestrator_status": orchestrator_status,
                }
            ],
        }

    except Exception as exc:
        await db.rollback()
        if isinstance(exc, HTTPException):
            raise
        logger.error("Error processing Azure Monitor webhook (error_type=%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Azure Monitor webhook notification could not be processed.",
        ) from exc

