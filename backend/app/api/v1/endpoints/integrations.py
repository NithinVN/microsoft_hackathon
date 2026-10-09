from __future__ import annotations

import ipaddress
import socket
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
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

CHECKOUT_FAILURE_THRESHOLD = 0.20
CHECKOUT_FAILURE_MIN_REQUESTS = 20


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _safe_url(value: str, *, allow_local: bool = False) -> str:
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

    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        if allow_local:
            return candidate
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Localhost targets are blocked outside the development/test environment.")

    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not resolve the hostname '{hostname}'.") from exc

    for family, _, _, _, sockaddr in resolved:
        ip_value = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_value)
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
            or getattr(ip, "is_site_local", False)
        ):
            if allow_local:
                continue
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Local, private, or internal network targets are blocked for security reasons.")
        if str(ip) in {"169.254.169.254"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metadata service and other internal addresses are blocked.")

    return candidate


def _base_metrics_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    base_path = parsed.path.rstrip("/")
    if base_path == "":
        return urljoin(base_url.rstrip("/") + "/", "metrics")
    return f"{base_url.rstrip('/')}/metrics"


def _base_health_url(base_url: str) -> str:
    parsed = urlsplit(base_url)
    base_path = parsed.path.rstrip("/")
    if base_path == "":
        return urljoin(base_url.rstrip("/") + "/", "health")
    return f"{base_url.rstrip('/')}/health"


def _coerce_float(raw_value: Any, *, default: float = 0.0) -> float:
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _checkout_failure_context(metrics: Dict[str, Any]) -> Dict[str, Any]:
    request_count = max(int(_coerce_float(metrics.get("request_count"), default=0.0)), 0)
    observed_error_rate = _coerce_float(metrics.get("error_rate"), default=0.0)
    configured_probability = max(
        _coerce_float(metrics.get("checkout_failure_probability"), default=0.0),
        _coerce_float(metrics.get("checkout_failure_rate"), default=0.0),
    )
    active_failure_modes = metrics.get("active_failure_modes") or []
    checkout_mode_enabled = configured_probability > 0.0 or "checkout_failures" in active_failure_modes

    if not checkout_mode_enabled:
        return {"state": "disabled", "request_count": request_count, "observed_error_rate": observed_error_rate, "configured_probability": configured_probability}
    if request_count < CHECKOUT_FAILURE_MIN_REQUESTS:
        return {"state": "insufficient_evidence", "request_count": request_count, "observed_error_rate": observed_error_rate, "configured_probability": configured_probability}
    if observed_error_rate > CHECKOUT_FAILURE_THRESHOLD:
        return {"state": "confirmed", "request_count": request_count, "observed_error_rate": observed_error_rate, "configured_probability": configured_probability}
    return {"state": "healthy", "request_count": request_count, "observed_error_rate": observed_error_rate, "configured_probability": configured_probability}


def _normalize_result_status(raw_value: Optional[str]) -> str:
    if raw_value is None:
        return "UNKNOWN"
    value = str(raw_value).strip().lower()
    if value in {"healthy", "ok", "up", "available", "success"}:
        return "HEALTHY"
    if value in {"degraded", "warning", "partial", "degraded-performance"}:
        return "DEGRADED"
    if value in {"unhealthy", "down", "unavailable", "failed", "error", "timeout"}:
        return "UNAVAILABLE"
    if value in {"unsupported", "not_supported", "not-supported"}:
        return "UNSUPPORTED"
    return "UNKNOWN"


async def _request_json(url: str, *, timeout_seconds: float, headers: Optional[Dict[str, str]] = None, max_redirects: int = 5) -> Dict[str, Any]:
    effective_headers = {"User-Agent": "IncidentMind-External-Integration/1.0", "Accept": "application/json"}
    if headers:
        effective_headers.update(headers)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds), follow_redirects=False) as client:
            current_url = _safe_url(url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
            redirect_history: List[Dict[str, str]] = []
            response = await client.get(current_url, headers=effective_headers)
            for _ in range(max_redirects):
                if 300 <= response.status_code < 400 and response.headers.get("location"):
                    next_url = urljoin(current_url, response.headers["location"])
                    next_url = _safe_url(next_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
                    redirect_history.append({"from": current_url, "to": next_url, "status": str(response.status_code)})
                    current_url = next_url
                    response = await client.get(current_url, headers=effective_headers)
                    continue
                break
            payload: Any = {}
            content_type = response.headers.get("content-type", "").lower()
            if "json" in content_type or response.text.startswith("{") or response.text.startswith("["):
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"raw": response.text[:2000]}
            elif response.text:
                payload = {"raw": response.text[:2000]}
            return {
                "ok": response.is_success,
                "status_code": response.status_code,
                "response_time_ms": int((response.elapsed.total_seconds() * 1000) if response.elapsed else 0),
                "payload": payload if isinstance(payload, dict) else {"raw": payload},
                "headers": dict(response.headers),
                "final_url": str(current_url),
                "redirects": redirect_history,
                "error": None,
            }
    except httpx.TimeoutException:
        return {
            "ok": False,
            "status_code": None,
            "response_time_ms": 0,
            "payload": {"error": "Connection timeout"},
            "headers": {},
            "final_url": url,
            "redirects": [],
            "error": "Connection timeout",
        }
    except (httpx.NetworkError, httpx.HTTPError, ValueError) as exc:
        return {
            "ok": False,
            "status_code": None,
            "response_time_ms": 0,
            "payload": {"error": str(exc)},
            "headers": {},
            "final_url": url,
            "redirects": [],
            "error": str(exc),
        }


async def _probe_integration(integration: ExternalWebsiteIntegration, *, api_key: Optional[str] = None) -> Dict[str, Any]:
    headers = {"User-Agent": "IncidentMind-External-Integration/1.0", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if integration.service_identifier:
        headers["X-Service-Identifier"] = integration.service_identifier

    endpoint = integration.health_url or integration.base_url
    timeout_seconds = 5.0
    result = await _request_json(endpoint, timeout_seconds=timeout_seconds, headers=headers)
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    health_status = _normalize_result_status(payload.get("status") if isinstance(payload, dict) else None)
    if result["status_code"] is None:
        status_label = "UNREACHABLE"
        reachable = False
    elif 300 <= result["status_code"] < 400:
        status_label = "UNREACHABLE"
        reachable = False
    elif 200 <= result["status_code"] < 300:
        reachable = True
        if health_status == "HEALTHY":
            status_label = "HEALTHY"
        elif health_status == "DEGRADED":
            status_label = "DEGRADED"
        elif health_status == "UNAVAILABLE":
            status_label = "UNAVAILABLE"
        elif health_status == "UNSUPPORTED":
            status_label = "UNSUPPORTED"
        else:
            status_label = "REACHABLE"
    elif 400 <= result["status_code"] < 600:
        reachable = True
        status_label = "UNAVAILABLE" if result["status_code"] >= 500 else "UNREACHABLE"
    else:
        reachable = True
        status_label = "REACHABLE"

    if result.get("error") and status_label == "REACHABLE":
        status_label = "UNREACHABLE"

    return {
        "status": status_label,
        "reachable": reachable,
        "http_status_code": result.get("status_code"),
        "response_time_ms": result.get("response_time_ms"),
        "timeout_seconds": timeout_seconds,
        "health_status": health_status if payload else "UNKNOWN",
        "health_payload": payload if isinstance(payload, dict) else {"raw": payload},
        "endpoint": endpoint,
        "final_url": result.get("final_url"),
        "redirects": result.get("redirects", []),
        "error": result.get("error"),
        "last_checked_at": _utcnow(),
    }


def _summary_from_metrics(data: Dict[str, Any]) -> Dict[str, str]:
    if not isinstance(data, dict):
        return {"overall": "UNKNOWN", "api": "UNKNOWN", "dependencies": "UNKNOWN", "database": "UNKNOWN"}

    dependency_status = _normalize_result_status(str(data.get("dependency_status") or "unknown"))
    db_pool = data.get("database_pool_usage_percent")
    error_rate = _coerce_float(data.get("error_rate"), default=0.0)
    checkout_context = _checkout_failure_context(data)

    overall = "HEALTHY"
    if dependency_status in {"UNAVAILABLE", "DOWN", "FAILED"}:
        overall = "UNAVAILABLE"
    elif checkout_context["state"] == "confirmed":
        overall = "UNAVAILABLE"
    elif dependency_status == "DEGRADED" or error_rate > 0.05 or checkout_context["state"] == "insufficient_evidence" or (isinstance(db_pool, (int, float)) and db_pool >= 70):
        overall = "DEGRADED"

    api_status = "HEALTHY"
    if data.get("average_response_time_ms") is not None:
        try:
            if float(data.get("average_response_time_ms")) > 1000 or error_rate > 0.05:
                api_status = "DEGRADED"
        except (TypeError, ValueError):
            api_status = "UNKNOWN"
    else:
        api_status = "UNKNOWN"

    database_status = "HEALTHY"
    if isinstance(db_pool, (int, float)):
        if db_pool >= 90:
            database_status = f"{int(db_pool)}% simulated utilization"
        elif db_pool >= 70:
            database_status = "DEGRADED"
    else:
        database_status = "UNKNOWN"

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
    dep_status_value = _normalize_result_status(dep_status)
    error_rate = metrics.get("error_rate")
    try:
        error_rate_value = float(error_rate) if error_rate is not None else 0.0
    except (TypeError, ValueError):
        error_rate_value = 0.0

    if dep_status_value in {"UNAVAILABLE", "DEGRADED"}:
        flaws.append(
            ExternalWebsiteFlaw(
                flaw_id="dependency-unavailable",
                title="Dependency unavailable",
                category="dependency",
                severity="HIGH",
                confidence=0.96,
                status="CONFIRMED",
                description="The monitored service is reporting a dependency problem that is affecting user-facing requests.",
                evidence=[f"Dependency status reported as {dep_status}", "Operational checks confirm the dependency is not healthy."],
                affected_endpoint="GET /dependency/status",
                observed_value=str(dep_status),
                expected_value="available",
                impact="Checkout and dependent requests may fail or slow down for customers.",
                likely_cause="The upstream dependency is unavailable or degraded.",
                recommended_action="Confirm the dependency status and restore the failing service before rerunning production traffic.",
            )
        )

    checkout_context = _checkout_failure_context(metrics)
    if checkout_context["state"] == "confirmed":
        flaws.append(
            ExternalWebsiteFlaw(
                flaw_id="checkout-failure-rate",
                title="Elevated checkout failure rate",
                category="availability",
                severity="HIGH",
                confidence=0.94,
                status="CONFIRMED",
                description="Checkout requests are failing at a rate consistent with a production-facing incident.",
                evidence=[
                    f"Observed checkout error rate: {checkout_context['observed_error_rate']:.2%}",
                    f"Observed checkout requests: {checkout_context['request_count']}",
                    f"Alert threshold: > {CHECKOUT_FAILURE_THRESHOLD:.0%}",
                ],
                affected_endpoint="POST /checkout",
                observed_value=f"{checkout_context['observed_error_rate']:.2%}",
                expected_value=f"< {CHECKOUT_FAILURE_THRESHOLD:.0%}",
                impact="Customers can experience order failures and revenue loss.",
                likely_cause="Checkout is surfacing a transient or persistent backend failure mode.",
                recommended_action="Inspect the checkout dependency, recent deployments, and any failing payment or fulfillment calls.",
            )
        )
    elif checkout_context["state"] == "insufficient_evidence":
        configured_probability = checkout_context["configured_probability"]
        flaws.append(
            ExternalWebsiteFlaw(
                flaw_id="checkout-failure-mode-inconclusive",
                title="Checkout failure mode enabled with insufficient observed evidence",
                category="availability",
                severity="LOW",
                confidence=0.62,
                status="INCONCLUSIVE",
                description="A checkout failure mode is configured, but there are not yet enough observed requests to confirm a sustained elevated failure rate.",
                evidence=[
                    f"Configured checkout failure probability: {configured_probability:.2%}",
                    f"Observed checkout requests: {checkout_context['request_count']}",
                    f"Minimum observations required: {CHECKOUT_FAILURE_MIN_REQUESTS}",
                    f"Confirmed alert threshold: observed error rate > {CHECKOUT_FAILURE_THRESHOLD:.0%}",
                ],
                affected_endpoint="POST /checkout",
                observed_value=f"{checkout_context['request_count']} requests observed; insufficient evidence",
                expected_value=f"at least {CHECKOUT_FAILURE_MIN_REQUESTS} requests and an observed error rate > {CHECKOUT_FAILURE_THRESHOLD:.0%}",
                impact="There may be a latent checkout issue, but the current evidence is not yet sufficient to confirm it as an active incident.",
                likely_cause="The checkout endpoint has a known failure mode configured or intentionally simulated, but the service has not yet accumulated enough valid traffic to confirm the observed rate.",
                recommended_action="Rerun the scan after additional checkout traffic or confirm the checkout dependency state before classifying the issue as confirmed.",
            )
        )

    if metrics.get("average_response_time_ms") is not None:
        try:
            latency_ms = float(metrics["average_response_time_ms"])
        except (TypeError, ValueError):
            latency_ms = None
        if latency_ms is not None and latency_ms > 1500:
            flaws.append(
                ExternalWebsiteFlaw(
                    flaw_id="slow-api-latency",
                    title="API latency elevated above safe threshold",
                    category="performance",
                    severity="MEDIUM",
                    confidence=0.8,
                    status="LIKELY",
                    description="The monitored API is responding slower than expected and may be affecting user experience.",
                    evidence=[f"Average response time observed: {latency_ms:.0f} ms", "The site is slower than the normal operational threshold."],
                    affected_endpoint="GET /products",
                    observed_value=f"{latency_ms:.0f} ms",
                    expected_value="< 1000 ms",
                    impact="User-facing requests may take longer than expected and degrade conversion.",
                    likely_cause="The application is experiencing sustained load or an upstream bottleneck.",
                    recommended_action="Review request latency trends and check slow downstream dependencies or database access patterns.",
                )
            )

    db_pool = metrics.get("database_pool_usage_percent")
    if isinstance(db_pool, (int, float)) and db_pool >= 90:
        flaws.append(
            ExternalWebsiteFlaw(
                flaw_id="database-utilization-high",
                title="Database utilization near saturation",
                category="database",
                severity="MEDIUM",
                confidence=0.82,
                status="LIKELY",
                description="The simulated database utilization is high enough to suggest contention or pool saturation.",
                evidence=[f"Database pool usage: {db_pool}%", "The threshold for a high-load signal has been crossed."],
                affected_endpoint="GET /metrics",
                observed_value=f"{db_pool}%",
                expected_value="< 85%",
                impact="The service may experience slower queries or connection queueing under load.",
                likely_cause="Database contention or an overloaded connection pool is restricting throughput.",
                recommended_action="Inspect the database pool metrics and correlate them with dependency failures or recent deployments.",
            )
        )

    if health and str(health.get("status") or "").lower() in {"degraded", "warning"} and not flaws:
        flaws.append(
            ExternalWebsiteFlaw(
                flaw_id="health-degraded",
                title="Service health degraded",
                category="status",
                severity="LOW",
                confidence=0.52,
                status="INCONCLUSIVE",
                description="The service is reachable but the health payload reports degraded status without confirmed root cause data.",
                evidence=["Health endpoint responded successfully", f"Health status reported as {health.get('status')}"],
                affected_endpoint="GET /health",
                observed_value=str(health.get("status")),
                expected_value="healthy",
                impact="The service may be operating in a degraded but not yet failed state.",
                likely_cause="A dependency or internal service is under stress or partially unavailable.",
                recommended_action="Review active dependency metrics and compare the health endpoint against recent deployment and alert activity.",
            )
        )

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
    url = _safe_url(payload.base_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
    if payload.health_url:
        _safe_url(payload.health_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
    if payload.metrics_url:
        _safe_url(payload.metrics_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
    if payload.webhook_url:
        _safe_url(payload.webhook_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    name = payload.name.strip()
    existing_name = await db.execute(select(ExternalWebsiteIntegration).where(func.lower(ExternalWebsiteIntegration.name) == name.lower()))
    if existing_name.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Integration '{name}' already exists. Reuse the existing integration or edit it from the list below.")

    existing_url = await db.execute(select(ExternalWebsiteIntegration).where(func.lower(ExternalWebsiteIntegration.base_url) == url.lower()))
    if existing_url.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A website integration for '{url}' already exists. Reuse the existing integration or edit it from the list below.")

    item = ExternalWebsiteIntegration(
        name=name,
        base_url=url,
        health_url=payload.health_url.strip() if payload.health_url else None,
        webhook_url=payload.webhook_url.strip() if payload.webhook_url else None,
        service_name=payload.service_name.strip() if payload.service_name else None,
        service_identifier=payload.service_identifier.strip() if payload.service_identifier else None,
        integration_method=payload.integration_method or "http",
        api_key_reference=("provided" if payload.api_key else None),
        metadata_json={"api_key_provided": bool(payload.api_key), "metrics_url": payload.metrics_url.strip() if payload.metrics_url else None},
        status="unverified",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    db.add(item)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Integration '{name}' already exists. Reuse the existing integration or edit it from the list below.") from exc
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


@router.put("/websites/{integration_id}", response_model=ExternalWebsiteIntegrationRead)
async def update_integration(
    integration_id: int,
    payload: ExternalWebsiteIntegrationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ExternalWebsiteIntegrationRead:
    item = await db.get(ExternalWebsiteIntegration, integration_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found.")

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Integration name cannot be empty.")
        duplicate = await db.execute(select(ExternalWebsiteIntegration).where(func.lower(ExternalWebsiteIntegration.name) == new_name.lower(), ExternalWebsiteIntegration.id != integration_id))
        if duplicate.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Integration '{new_name}' already exists. Reuse the existing integration or edit it from the list below.")
        item.name = new_name

    if payload.base_url is not None:
        item.base_url = _safe_url(payload.base_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    if payload.health_url is not None:
        item.health_url = payload.health_url.strip() or None
        if item.health_url:
            _safe_url(item.health_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    if payload.metrics_url is not None:
        value = payload.metrics_url.strip() or None
        item.metadata_json = {**item.metadata_json, "metrics_url": value}

    if payload.webhook_url is not None:
        item.webhook_url = payload.webhook_url.strip() or None
        if item.webhook_url:
            _safe_url(item.webhook_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    if payload.service_name is not None:
        item.service_name = payload.service_name.strip() or None
    if payload.service_identifier is not None:
        item.service_identifier = payload.service_identifier.strip() or None
    if payload.metadata_json is not None:
        item.metadata_json = {**item.metadata_json, **payload.metadata_json}

    if payload.base_url is not None or payload.health_url is not None or payload.metrics_url is not None:
        item.status = "unverified"
        item.last_checked_at = None
        item.last_response_time_ms = None
        item.last_status_code = None
        item.last_error = "Configuration updated. Re-test and re-scan to refresh connection and health results."

    item.updated_at = _utcnow()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Integration '{item.name}' already exists. Reuse the existing integration or edit it from the list below.") from exc
    await db.refresh(item)
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
    _safe_url(item.base_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
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
    _safe_url(item.base_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    metrics_url = (item.metadata_json or {}).get("metrics_url") or None
    if not metrics_url:
        hostname = (urlsplit(item.base_url).hostname or "").lower()
        service_hint = f"{item.name} {item.service_name or ''}".lower()
        if hostname in {"localhost", "127.0.0.1", "::1"} or any(term in service_hint for term in ("demo", "shop")):
            metrics_url = _base_metrics_url(item.base_url)
    if item.health_url:
        _safe_url(item.health_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
    elif any(term in f"{item.name} {item.service_name or ''}".lower() for term in ("demo", "shop")) or (urlsplit(item.base_url).hostname or "").lower() in {"localhost", "127.0.0.1", "::1"}:
        item.health_url = _base_health_url(item.base_url)
        _safe_url(item.health_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})
    if metrics_url:
        _safe_url(metrics_url, allow_local=settings.APP_ENV.lower() in {"development", "test"})

    checks_performed: List[str] = ["connection_check"]
    checks_skipped: List[str] = []
    default_health_result = await _probe_integration(item)
    health_payload = default_health_result.get("health_payload") if isinstance(default_health_result.get("health_payload"), dict) else {}
    health_status = default_health_result.get("health_status") or "UNKNOWN"
    if item.health_url:
        checks_performed.append("health_endpoint_check")
    else:
        checks_skipped.append("health_endpoint_check: no custom health endpoint configured")

    metrics_payload: Dict[str, Any] = {}
    if metrics_url:
        metrics_result = await _request_json(metrics_url, timeout_seconds=5.0, headers={"User-Agent": "IncidentMind-External-Integration/1.0"})
        if metrics_result.get("ok") and isinstance(metrics_result.get("payload"), dict):
            metrics_payload = metrics_result["payload"]
            checks_performed.append("metrics_check")
        else:
            checks_skipped.append(f"metrics_check: {metrics_result.get('error') or 'metrics endpoint unavailable'}")
    else:
        checks_skipped.append("metrics_check: no metrics endpoint configured")

    if not item.health_url and not metrics_url and default_health_result.get("reachable"):
        checks_performed.append("basic_website_check")

    summary = _summary_from_metrics(metrics_payload) if metrics_payload else {"overall": "UNKNOWN", "api": "UNKNOWN", "dependencies": "UNKNOWN", "database": "UNKNOWN"}
    flaws = _make_flaws(item.service_name or item.name, health_payload, metrics_payload)
    if not flaws and default_health_result.get("status") == "HEALTHY":
        summary["overall"] = "HEALTHY"
    if not flaws and default_health_result.get("status") == "REACHABLE":
        summary["overall"] = "REACHABLE"
    if not flaws and not metrics_payload and not item.health_url:
        summary["overall"] = "REACHABLE"
    if not flaws and default_health_result.get("status") == "UNSUPPORTED":
        summary["overall"] = "UNSUPPORTED"

    overall_status = summary["overall"]
    if not flaws and overall_status not in {"HEALTHY", "DEGRADED", "UNAVAILABLE", "REACHABLE", "UNSUPPORTED", "UNKNOWN"}:
        overall_status = "UNKNOWN"
    if flaws:
        if any(flaw.severity == "HIGH" for flaw in flaws):
            overall_status = "UNAVAILABLE"
        elif any(flaw.severity == "MEDIUM" for flaw in flaws):
            overall_status = "DEGRADED"
        else:
            overall_status = "HEALTHY"

    if overall_status == "HEALTHY" and health_status in {"UNKNOWN", "UNSUPPORTED"}:
        overall_status = "REACHABLE"

    now = _utcnow()
    evidence_summary = [
        f"Connection status: {default_health_result.get('status', 'UNKNOWN')}",
        f"Health status: {health_status}",
        f"Dependency status: {summary.get('dependencies', 'UNKNOWN')}",
        f"Database status: {summary.get('database', 'UNKNOWN')}",
    ]
    if flaws:
        evidence_summary.append("Current findings: active")
    else:
        evidence_summary.append("No issues detected by the checks performed.")

    scanned = ExternalWebsiteScanResult(
        integration_id=item.id,
        service=item.service_name or item.name,
        overall_status=overall_status,
        health_status=health_status,
        api_status=summary.get("api", "UNKNOWN"),
        dependencies_status=summary.get("dependencies", "UNKNOWN"),
        database_status=summary.get("database", "UNKNOWN"),
        http_status_code=default_health_result.get("http_status_code"),
        response_time_ms=default_health_result.get("response_time_ms"),
        incident_id=None,
        detected_flaws=flaws,
        evidence_summary=evidence_summary,
        checks_performed=checks_performed,
        checks_skipped=checks_skipped,
        last_checked_at=now,
        raw_data={"health": health_payload, "metrics": metrics_payload, "connection": default_health_result},
    )

    item.status = scanned.overall_status
    item.last_checked_at = now
    item.last_response_time_ms = scanned.response_time_ms
    item.last_status_code = scanned.http_status_code
    item.last_error = None if not flaws else flaws[0].title
    item.updated_at = now
    await db.commit()

    created_incident_id = await _upsert_incident_for_scan(db, item, scanned)
    if created_incident_id is not None:
        scanned.incident_id = created_incident_id
        item.metadata_json = {**(item.metadata_json or {}), "incident_id": created_incident_id, "scan_status": scanned.overall_status}
        await db.commit()
    return scanned


@router.delete("/websites/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(integration_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    await _delete_integration(db, integration_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
