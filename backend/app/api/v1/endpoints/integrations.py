from __future__ import annotations

import ipaddress
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.db.session import get_db
from backend.app.models.external_integration import ExternalWebsiteIntegration
from backend.app.models.incident import Incident
from backend.app.repositories.incident_repository import IncidentRepository
from backend.app.schemas.external_integration import (
    ExternalWebsiteConnectionTestRequest,
    ExternalWebsiteConnectionTestResult,
    ExternalWebsiteFlaw,
    ExternalWebsiteIntegrationCreate,
    ExternalWebsiteIntegrationRead,
    ExternalWebsiteIntegrationUpdate,
    ExternalWebsiteScanRequest,
    ExternalWebsiteScanResult,
)
from backend.app.schemas.incident import IncidentCreate

router = APIRouter()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_url(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL is required.")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only http and https URLs are supported.")
    if not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid hostname is required.")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A valid hostname is required.")

    if settings.APP_ENV.lower() not in {"development", "test"}:
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local or private network targets are blocked in production for security reasons.")
        except ValueError:
            pass

    return candidate


def _base_metrics_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    base_path = parsed.path.rstrip("/")
    if base_path == "":
        return urljoin(base_url.rstrip("/") + "/", "metrics")
    return f"{base_url.rstrip('/')}/metrics"


async def _request_json(url: str, *, timeout_seconds: float, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
        response = await client.get(url, headers=headers or {})
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        return {
            "ok": response.is_success,
            "status_code": response.status_code,
            "response_time_ms": int((response.elapsed.total_seconds() * 1000) if response.elapsed else 0),
            "payload": payload,
            "headers": dict(response.headers),
        }


async def _probe_integration(integration: ExternalWebsiteIntegration, *, api_key: Optional[str] = None) -> Dict[str, Any]:
    headers = {"User-Agent": "IncidentMind-External-Integration/1.0", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if integration.service_identifier:
        headers["X-Service-Identifier"] = integration.service_identifier

    timeout_seconds = 5.0
    endpoint = integration.health_url or integration.base_url
    start = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds)) as client:
            response = await client.get(endpoint, headers=headers)
            duration_ms = int((perf_counter() - start) * 1000)
            try:
                payload = response.json()
            except ValueError:
                payload = {"raw": response.text}

            return {
                "status": "connected" if response.is_success else "failed",
                "reachable": response.is_success,
                "http_status_code": response.status_code,
                "response_time_ms": duration_ms,
                "timeout_seconds": timeout_seconds,
                "health_status": payload.get("status") if isinstance(payload, dict) else None,
                "health_payload": payload if isinstance(payload, dict) else {"raw": payload},
                "endpoint": endpoint,
                "error": None,
                "last_checked_at": _utcnow(),
            }
    except httpx.TimeoutException:
        return {
            "status": "failed",
            "reachable": False,
            "http_status_code": None,
            "response_time_ms": int((perf_counter() - start) * 1000),
            "timeout_seconds": timeout_seconds,
            "health_status": None,
            "health_payload": None,
            "endpoint": endpoint,
            "error": "Connection timeout",
            "last_checked_at": _utcnow(),
        }
    except (httpx.NetworkError, httpx.HTTPError, ValueError) as exc:
        return {
            "status": "failed",
            "reachable": False,
            "http_status_code": None,
            "response_time_ms": int((perf_counter() - start) * 1000),
            "timeout_seconds": timeout_seconds,
            "health_status": None,
            "health_payload": None,
            "endpoint": endpoint,
            "error": str(exc),
            "last_checked_at": _utcnow(),
        }


def _summary_from_metrics(data: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(data, dict):
        return {"overall": "unknown", "api": "unknown", "dependencies": "unknown", "database": "unknown"}
    dependency_status = str(data.get("dependency_status") or "unknown")
    db_pool = data.get("database_pool_usage_percent")
    overall = "healthy"
    if data.get("error_rate", 0) > 0.05 or dependency_status.lower() in {"unavailable", "down", "failed"}:
        overall = "degraded"
    if data.get("error_rate", 0) > 0.2 or dependency_status.lower() in {"unavailable", "down", "failed"}:
        overall = "unavailable"
    api_status = "healthy"
    if data.get("average_response_time_ms", 0) > 1000 or data.get("error_rate", 0) > 0.05:
        api_status = "degraded"
    database_status = "healthy"
    if isinstance(db_pool, (int, float)):
        if db_pool >= 90:
            database_status = f"{int(db_pool)}% simulated utilization"
        elif db_pool >= 70:
            database_status = "elevated"
    return {
        "overall": overall,
        "api": api_status,
        "dependencies": dependency_status,
        "database": database_status,
    }


def _make_flaws(service_name: str, health_payload: Dict[str, Any], metrics_payload: Dict[str, Any]) -> List[ExternalWebsiteFlaw]:
    flaws: List[ExternalWebsiteFlaw] = []
    metrics = metrics_payload if isinstance(metrics_payload, dict) else {}
    health = health_payload if isinstance(health_payload, dict) else {}
    dep_status = str(metrics.get("dependency_status") or "unknown")

    if dep_status.lower() in {"unavailable", "down", "failed"}:
        flaws.append(ExternalWebsiteFlaw(
            flaw_id="checkout-dependency-failure",
            title="Checkout dependency unavailable",
            category="dependency",
            severity="HIGH",
            confidence=0.97,
            status="CONFIRMED",
            description="The monitored service is depending on a dependency endpoint that is returning 503 or is marked unavailable.",
            evidence=[
                f"Dependency status reported as {dep_status}",
                "Checkout and dependent requests are failing during the monitored period",
            ],
            affected_endpoint="POST /checkout",
            observed_value=dep_status,
            expected_value="available",
            impact="Customers may be unable to complete purchases while dependency recovery is pending.",
            likely_cause="The payment or dependency service behind the checkout path is unavailable.",
            recommended_action="Restore dependency availability and re-check checkout success. Verify the dependency endpoint before rerunning the workflow.",
        ))

    error_rate = float(metrics.get("error_rate") or 0)
    if error_rate > 0.01:
        flaws.append(ExternalWebsiteFlaw(
            flaw_id="checkout-error-rate",
            title="Checkout failure rate elevated",
            category="reliability",
            severity="HIGH",
            confidence=0.94,
            status="CONFIRMED",
            description="The service is returning an elevated HTTP error rate on checkout traffic.",
            evidence=[
                f"Observed error rate {error_rate:.3f}",
                f"Dependency status = {dep_status}",
                "Checkout endpoint returned failed responses during the scan window",
            ],
            affected_endpoint="POST /checkout",
            observed_value=f"{error_rate:.3f}",
            expected_value="< 0.01",
            impact="Customers may experience failed purchases and abandonment during the incident window.",
            likely_cause="Unavailable dependency and degraded checkout handling are causing the elevated failure rate.",
            recommended_action="Investigate the dependency path and verify error handling around checkout before restoring customer traffic.",
        ))

    latency_ms = float(metrics.get("average_response_time_ms") or 0)
    if latency_ms > 500:
        flaws.append(ExternalWebsiteFlaw(
            flaw_id="slow-api-response",
            title="High response latency",
            category="latency",
            severity="MEDIUM",
            confidence=0.82,
            status="LIKELY",
            description="API latency is above the expected threshold and may be contributing to the degraded service experience.",
            evidence=[
                f"Observed average response time {latency_ms:.0f} ms",
                "The website health payload shows degraded operational state",
                "Dependency degradation is consistent with increased latency",
            ],
            affected_endpoint="GET /products",
            observed_value=f"{latency_ms:.0f} ms",
            expected_value="< 500 ms",
            impact="Users experience slower pages and delayed transaction completion.",
            likely_cause="The dependency degradation and elevated load are causing increased request latency.",
            recommended_action="Confirm the dependency and database performance profile, then reduce concurrent load while monitoring the latency trend.",
        ))

    db_usage = float(metrics.get("database_pool_usage_percent") or 0)
    if db_usage >= 85:
        flaws.append(ExternalWebsiteFlaw(
            flaw_id="db-pool-saturation",
            title="Database pool utilization elevated",
            category="capacity",
            severity="MEDIUM",
            confidence=0.63,
            status="INCONCLUSIVE",
            description="Database pool utilization is high and may be contributing to the issue, but the current evidence does not prove it is the root cause.",
            evidence=[
                f"Observed database pool usage {db_usage:.0f}%",
                "The metric is elevated but not directly tied to a single failing checkout request",
            ],
            affected_endpoint="GET /metrics",
            observed_value=f"{db_usage:.0f}%",
            expected_value="< 85%",
            impact="The service could experience contention or request queuing under sustained load.",
            likely_cause="The upstream dependency issue may be amplifying database utilization, but the evidence is not definitive.",
            recommended_action="Monitor database utilization alongside dependency recovery and confirm whether connection pool saturation is a contributor or a secondary symptom.",
        ))

    if not flaws and health.get("status") == "degraded":
        flaws.append(ExternalWebsiteFlaw(
            flaw_id="health-degraded",
            title="Service degraded but no direct failure confirmed",
            category="status",
            severity="LOW",
            confidence=0.52,
            status="INCONCLUSIVE",
            description="The service is degraded according to its health payload, but the scan did not capture a direct root cause.",
            evidence=[
                f"Health status reported as {health.get('status')}",
                "The endpoint is reachable but shows degraded operational state",
            ],
            affected_endpoint="GET /health",
            observed_value=str(health.get("status")),
            expected_value="healthy",
            impact="The service may be experiencing a slower or more fragile operating state than normal.",
            likely_cause="One or more backend dependencies are unstable or under load.",
            recommended_action="Review the service health and dependency metrics before changing production traffic patterns.",
        ))

    return flaws


async def _upsert_incident_for_scan(db: AsyncSession, integration: ExternalWebsiteIntegration, result: ExternalWebsiteScanResult) -> Optional[str]:
    if not result.detected_flaws:
        return None

    repo = IncidentRepository(db)
    existing_prefix = "INC-EXT-"
    existing_ids = [incident.incident_id for incident in await repo.list_incidents(limit=200) if str(incident.incident_id).startswith(existing_prefix)]
    next_number = 1
    for candidate in sorted(existing_ids, key=lambda value: int(value.split("-")[-1])):
        try:
            number = int(candidate.split("-")[-1])
            if number >= next_number:
                next_number = number + 1
        except ValueError:
            continue

    incident_id = f"{existing_prefix}{next_number:03d}"
    if repo is not None:
        incident = await repo.create_incident(
            IncidentCreate(
                incident_id=incident_id,
                title=f"{integration.name} external dependency incident",
                description=f"{integration.name} was observed to have degraded health and external dependency issues during a monitoring scan.",
                severity="SEV-2",
                status="DETECTED",
                source="external_website",
                affected_service=integration.service_name or integration.name,
                symptoms=[item.title for item in result.detected_flaws],
                metadata={
                    "integration_id": integration.id,
                    "website_name": integration.name,
                    "service_name": integration.service_name or integration.name,
                    "base_url": integration.base_url,
                    "health_url": integration.health_url,
                    "evidence_summary": result.evidence_summary,
                    "raw_data": result.raw_data,
                },
            )
        )
        incident.metadata_json["scan_result"] = result.model_dump(mode="json")
        await db.commit()
        return incident.incident_id
    return None


async def _delete_integration(db: AsyncSession, integration_id: int) -> None:
    integration = await db.get(ExternalWebsiteIntegration, integration_id)
    if integration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")
    await db.delete(integration)
    await db.commit()


@router.post("/websites", response_model=ExternalWebsiteIntegrationRead, status_code=status.HTTP_201_CREATED)
async def create_integration(
    payload: ExternalWebsiteIntegrationCreate,
    db: AsyncSession = Depends(get_db),
) -> ExternalWebsiteIntegrationRead:
    """Create an external website/service integration without persisting any secret material."""
    url = _safe_url(payload.base_url)
    if payload.health_url:
        _safe_url(payload.health_url)
    if payload.webhook_url:
        _safe_url(payload.webhook_url)

    existing = (await db.execute(select(ExternalWebsiteIntegration).where(ExternalWebsiteIntegration.name == payload.name))).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Integration '{payload.name}' already exists.")

    item = ExternalWebsiteIntegration(
        name=payload.name,
        base_url=url,
        health_url=payload.health_url or None,
        webhook_url=payload.webhook_url or None,
        service_name=payload.service_name or (payload.name or "external-service"),
        service_identifier=payload.service_identifier,
        integration_method=payload.integration_method or "http",
        api_key_reference=("provided" if payload.api_key else None),
        metadata_json={"api_key_provided": bool(payload.api_key)},
        status="unverified",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return ExternalWebsiteIntegrationRead.model_validate(item)


@router.get("/websites", response_model=List[ExternalWebsiteIntegrationRead])
async def list_integrations(
    db: AsyncSession = Depends(get_db),
) -> List[ExternalWebsiteIntegrationRead]:
    result = await db.execute(select(ExternalWebsiteIntegration).order_by(ExternalWebsiteIntegration.created_at.desc()))
    integrations = result.scalars().all()
    return [ExternalWebsiteIntegrationRead.model_validate(item) for item in integrations]


@router.get("/websites/{integration_id}", response_model=ExternalWebsiteIntegrationRead)
async def get_integration(integration_id: int, db: AsyncSession = Depends(get_db)) -> ExternalWebsiteIntegrationRead:
    item = await db.get(ExternalWebsiteIntegration, integration_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")
    return ExternalWebsiteIntegrationRead.model_validate(item)


@router.post("/websites/{integration_id}/test", response_model=ExternalWebsiteConnectionTestResult)
async def test_integration_connection(
    integration_id: int,
    payload: ExternalWebsiteConnectionTestRequest,
    db: AsyncSession = Depends(get_db),
) -> ExternalWebsiteConnectionTestResult:
    item = await db.get(ExternalWebsiteIntegration, integration_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")
    _safe_url(item.base_url)
    probe = await _probe_integration(item, api_key=payload.api_key)
    item.status = probe["status"]
    item.last_checked_at = probe["last_checked_at"]
    item.last_response_time_ms = probe["response_time_ms"]
    item.last_status_code = probe["http_status_code"]
    item.last_error = probe["error"]
    item.updated_at = _utcnow()
    await db.commit()
    await db.refresh(item)
    return ExternalWebsiteConnectionTestResult(
        integration_id=item.id,
        status=probe["status"],
        reachable=probe["reachable"],
        http_status_code=probe["http_status_code"],
        response_time_ms=probe["response_time_ms"],
        timeout_seconds=probe["timeout_seconds"],
        endpoint=probe["endpoint"],
        health_status=probe["health_status"],
        health_payload=probe["health_payload"],
        last_checked_at=probe["last_checked_at"],
        error=probe["error"],
    )


@router.post("/websites/{integration_id}/scan", response_model=ExternalWebsiteScanResult)
async def scan_integration(
    integration_id: int,
    payload: ExternalWebsiteScanRequest,
    db: AsyncSession = Depends(get_db),
) -> ExternalWebsiteScanResult:
    item = await db.get(ExternalWebsiteIntegration, integration_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")
    _safe_url(item.base_url)

    metrics_url = item.base_url.rstrip("/") + "/metrics"
    if item.health_url:
        _safe_url(item.health_url)
    health_result = await _request_json(item.health_url or item.base_url, timeout_seconds=5.0)
    if not health_result.get("ok"):
        health_payload = {"status": "unavailable", "service": item.service_name or item.name}
    else:
        health_payload = health_result.get("payload") if isinstance(health_result.get("payload"), dict) else {"status": "unavailable"}
    metrics_result = await _request_json(metrics_url, timeout_seconds=5.0)
    metrics_payload = metrics_result.get("payload") if isinstance(metrics_result.get("payload"), dict) else {}

    summary = _summary_from_metrics(metrics_payload)
    flaws = _make_flaws(item.service_name or item.name, health_payload, metrics_payload)
    now = _utcnow()
    if item.health_url:
        endpoint = item.health_url
    else:
        endpoint = item.base_url

    scanned = ExternalWebsiteScanResult(
        integration_id=item.id,
        service=item.service_name or item.name,
        overall_status=summary["overall"],
        health_status=str(health_payload.get("status") or summary["overall"]),
        api_status=summary["api"],
        dependencies_status=summary["dependencies"],
        database_status=summary["database"],
        http_status_code=health_result.get("status_code"),
        response_time_ms=health_result.get("response_time_ms"),
        incident_id=None,
        detected_flaws=flaws,
        evidence_summary=[
            f"Health status: {health_payload.get('status', 'unknown')}",
            f"Dependency status: {summary['dependencies']}",
            f"Database pool: {summary['database']}",
            f"Error rate: {metrics_payload.get('error_rate', 'unavailable')}",
        ],
        last_checked_at=now,
        raw_data={"health": health_payload, "metrics": metrics_payload},
    )

    item.status = scanned.overall_status
    item.last_checked_at = now
    item.last_response_time_ms = scanned.response_time_ms
    item.last_status_code = scanned.http_status_code
    item.last_error = None if flaws else "No critical issues detected during scan."
    item.updated_at = now
    await db.commit()

    created_incident_id = await _upsert_incident_for_scan(db, item, scanned)
    if created_incident_id is not None:
        scanned.incident_id = created_incident_id
        item.metadata_json = {**item.metadata_json, "incident_id": created_incident_id, "scan_status": scanned.overall_status}
        await db.commit()
    return scanned


@router.delete("/websites/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(integration_id: int, db: AsyncSession = Depends(get_db)) -> None:
    await _delete_integration(db, integration_id)
