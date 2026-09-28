"""Hindsight Cloud Organizational Memory Service for IncidentMind.

This service interfaces directly with the official Hindsight SDK/API (`hindsight-client`)
to provide long-term institutional memory across incident triage, root cause analysis,
remediation evaluations, engineer feedback, and postmortems.

Architectural Rule:
- PostgreSQL stores operational application state.
- Hindsight Cloud stores persistent organizational memory and performs semantic, entity,
  and temporal reasoning (Retain, Recall, Reflect).
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Union

try:
    from hindsight_client import Hindsight
    from hindsight_client_api.exceptions import ApiException
    HINDSIGHT_CLIENT_AVAILABLE = True
except ImportError:
    Hindsight = None  # type: ignore
    ApiException = Exception  # type: ignore
    HINDSIGHT_CLIENT_AVAILABLE = False

from backend.app.core.config import settings
from backend.app.core.logging import logger


class HindsightService:
    """Enterprise organizational memory service powered by official Hindsight Cloud SDK."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        bank_id: Optional[str] = None,
        timeout: Optional[float] = None,
        max_attempts: Optional[int] = None,
    ) -> None:
        self.base_url = (base_url or settings.HINDSIGHT_BASE_URL).rstrip("/")
        self.api_key = api_key if api_key is not None else settings.HINDSIGHT_API_KEY
        self.bank_id = bank_id or settings.HINDSIGHT_BANK_ID
        self.timeout = timeout or settings.HINDSIGHT_TIMEOUT_SECONDS
        self.max_attempts = max_attempts or settings.HINDSIGHT_MAX_RETRIES
        self._client: Optional[Hindsight] = None

    @property
    def is_configured(self) -> bool:
        """Returns True if minimum configuration is provided."""
        return bool(self.base_url and self.bank_id)

    def close(self) -> None:
        """Closes any underlying connection pools and HTTP sessions."""
        if self._client is not None:
            try:
                if hasattr(self._client, "close"):
                    self._client.close()
            except Exception as exc:
                logger.debug("Error closing Hindsight client", extra={"error": str(exc)})
            finally:
                self._client = None

    async def aclose(self) -> None:
        """Asynchronously closes any underlying connection pools."""
        if self._client is not None:
            try:
                if hasattr(self._client, "aclose"):
                    await self._client.aclose()
                elif hasattr(self._client, "close"):
                    self._client.close()
            except Exception as exc:
                logger.debug("Error asynchronously closing Hindsight client", extra={"error": str(exc)})
            finally:
                self._client = None

    def get_client(self) -> Optional[Hindsight]:
        """Lazy initializer for official Hindsight client with connection configuration."""
        if self._client is not None:
            return self._client

        if not HINDSIGHT_CLIENT_AVAILABLE:
            logger.warning(
                "Hindsight client SDK (hindsight-client) is not installed or available.",
                extra={"base_url": self.base_url},
            )
            return None

        try:
            logger.info(
                "Initializing official Hindsight client",
                extra={
                    "base_url": self.base_url,
                    "bank_id": self.bank_id,
                    "timeout": self.timeout,
                    "max_attempts": self.max_attempts,
                },
            )
            self._client = Hindsight(
                base_url=self.base_url,
                api_key=self.api_key if self.api_key else None,
                timeout=self.timeout,
                max_attempts=self.max_attempts,
            )
            return self._client
        except Exception as exc:
            logger.error(
                "Failed to instantiate Hindsight client",
                extra={"error": str(exc), "base_url": self.base_url},
                exc_info=True,
            )
            return None

    # =========================================================================
    # Health Check & Diagnostic Operations
    # =========================================================================

    def check_health(self) -> Dict[str, Any]:
        """Performs health check on Hindsight Cloud connection.

        Hindsight API Method:
            - `Hindsight.get_version()`
            - `Hindsight.get_bank_config(bank_id=...)`
        """
        if not HINDSIGHT_CLIENT_AVAILABLE:
            return {
                "healthy": False,
                "status": "missing_sdk",
                "message": "hindsight-client package is not installed.",
                "base_url": self.base_url,
                "bank_id": self.bank_id,
            }

        client = self.get_client()
        if not client:
            return {
                "healthy": False,
                "status": "uninitialized",
                "message": "Hindsight client could not be initialized.",
                "base_url": self.base_url,
                "bank_id": self.bank_id,
            }

        try:
            # Check service version
            version_resp = client.get_version()
            version_str = getattr(version_resp, "version", "unknown") if version_resp else "unknown"

            # Check memory bank access
            bank_info = {}
            try:
                bank_info = client.get_bank_config(bank_id=self.bank_id) or {}
            except Exception as bank_exc:
                logger.debug(
                    "Memory bank not yet created or inaccessible",
                    extra={"bank_id": self.bank_id, "error": str(bank_exc)},
                )

            return {
                "healthy": True,
                "status": "connected",
                "version": version_str,
                "base_url": self.base_url,
                "bank_id": self.bank_id,
                "bank_configured": bool(bank_info),
            }
        except ApiException as api_err:
            logger.warning(
                "Hindsight API returned error during health check",
                extra={"status": api_err.status if hasattr(api_err, "status") else None, "error": str(api_err)},
            )
            return {
                "healthy": False,
                "status": "api_error",
                "status_code": getattr(api_err, "status", None),
                "error": str(api_err),
                "base_url": self.base_url,
                "bank_id": self.bank_id,
            }
        except Exception as exc:
            logger.warning(
                "Hindsight connection check failed",
                extra={"error": str(exc), "base_url": self.base_url},
            )
            return {
                "healthy": False,
                "status": "unreachable",
                "error": str(exc),
                "base_url": self.base_url,
                "bank_id": self.bank_id,
            }

    # =========================================================================
    # 1. Create Memory Bank
    # =========================================================================

    def create_memory_bank(
        self,
        bank_id: Optional[str] = None,
        name: Optional[str] = None,
        mission: Optional[str] = None,
        disposition_skepticism: int = 3,
        disposition_literalism: int = 3,
        disposition_empathy: int = 3,
    ) -> Dict[str, Any]:
        """Creates or initializes the dedicated IncidentMind organizational memory bank.

        Hindsight API Method:
            - `Hindsight.create_bank(bank_id=..., name=..., mission=...)`
        """
        target_bank = bank_id or self.bank_id
        target_name = name or f"IncidentMind Organizational Memory ({target_bank})"
        target_mission = (
            mission
            or "Institutional memory for site reliability engineering, root cause analysis, "
            "remediation verification, and postmortem learning."
        )

        client = self.get_client()
        if not client:
            return {"success": False, "bank_id": target_bank, "error": "Client not initialized"}

        try:
            logger.info("Creating or connecting to Hindsight memory bank", extra={"bank_id": target_bank})
            response = client.create_bank(
                bank_id=target_bank,
                name=target_name,
                mission=target_mission,
                disposition_skepticism=disposition_skepticism,
                disposition_literalism=disposition_literalism,
                disposition_empathy=disposition_empathy,
                enable_text_search=True,
                enable_temporal_retrieval=True,
                enable_graph_retrieval=True,
                enable_reranking=True,
            )
            return {
                "success": True,
                "bank_id": target_bank,
                "name": target_name,
                "created": True,
                "details": response.to_dict() if hasattr(response, "to_dict") else str(response),
            }
        except ApiException as api_err:
            # If bank already exists (e.g., status 400 or 409 or similar), verify bank config
            if hasattr(api_err, "status") and api_err.status in (400, 409):
                logger.info(
                    "Hindsight memory bank already exists, verified connection",
                    extra={"bank_id": target_bank, "status": api_err.status},
                )
                try:
                    config = client.get_bank_config(bank_id=target_bank)
                    return {"success": True, "bank_id": target_bank, "created": False, "details": config}
                except Exception:
                    return {"success": True, "bank_id": target_bank, "created": False}
            logger.error("ApiException creating Hindsight memory bank", extra={"error": str(api_err), "bank_id": target_bank})
            return {"success": False, "bank_id": target_bank, "error": str(api_err)}
        except Exception as exc:
            logger.error("Error creating Hindsight memory bank", extra={"error": str(exc), "bank_id": target_bank}, exc_info=True)
            return {"success": False, "bank_id": target_bank, "error": str(exc)}

    # =========================================================================
    # 2. Retain Incident
    # =========================================================================

    def retain_incident(
        self,
        incident_data: Dict[str, Any],
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains complete rich incident context into Hindsight memory.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        incident_id = incident_data.get("incident_id", "INC-UNKNOWN")
        service = incident_data.get("affected_service", "general")
        severity = incident_data.get("severity", "medium")
        status = incident_data.get("status", "resolved")
        title = incident_data.get("title", "Untitled Incident")
        description = incident_data.get("description", "")
        symptoms = incident_data.get("symptoms", [])
        root_cause = incident_data.get("root_cause", "Under investigation")
        resolution = incident_data.get("resolution", "")
        telemetry = incident_data.get("telemetry", {})
        logs = incident_data.get("logs", [])

        # Construct structured content narrative for Hindsight cognitive entity extraction
        content_lines = [
            f"# Production Incident Record: {incident_id} - {title}",
            f"**Service:** {service} | **Severity:** {severity} | **Status:** {status}",
            f"**Detected At:** {incident_data.get('detected_at', datetime.now(timezone.utc).isoformat())}",
            "",
            "## Description & Summary",
            description,
            "",
            "## Observed Symptoms",
        ]
        if isinstance(symptoms, list):
            for s in symptoms:
                content_lines.append(f"- {s}")
        else:
            content_lines.append(f"- {symptoms}")

        if root_cause:
            content_lines.extend(["", "## Root Cause Analysis", root_cause])

        if resolution:
            content_lines.extend(["", "## Applied Resolution", resolution])

        if logs:
            content_lines.extend(["", "## Diagnostic Log Excerpts"])
            for log_entry in (logs[:5] if isinstance(logs, list) else [logs]):
                content_lines.append(f"```\n{log_entry}\n```")

        content = "\n".join(content_lines)

        tags = [
            "incident",
            f"service:{service.lower()}",
            f"severity:{severity.lower()}",
            f"status:{status.lower()}",
            f"incident:{incident_id}",
        ]

        metadata = {
            "incident_id": str(incident_id),
            "service": str(service),
            "severity": str(severity),
            "status": str(status),
            "type": "incident_record",
            "retained_at": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=tags,
            metadata=metadata,
            document_id=f"incident-{incident_id}",
        )

    # =========================================================================
    # 3. Retain Root Cause
    # =========================================================================

    def retain_root_cause(
        self,
        incident_id: str,
        service: str,
        root_cause: str,
        evidence: Optional[Dict[str, Any]] = None,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains identified root cause and forensic evidence in Hindsight.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        content_lines = [
            f"# Root Cause Knowledge: Incident {incident_id} ({service})",
            f"**Service Affected:** {service}",
            "",
            "## Diagnosed Root Cause",
            root_cause,
        ]

        if evidence:
            content_lines.extend([
                "",
                "## Forensic Supporting Evidence",
                f"```json\n{json.dumps(evidence, indent=2)}\n```",
            ])

        content = "\n".join(content_lines)
        tags = [
            "root_cause",
            f"service:{service.lower()}",
            f"incident:{incident_id}",
        ]
        metadata = {
            "incident_id": incident_id,
            "service": service,
            "type": "root_cause",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=tags,
            metadata=metadata,
            document_id=f"rootcause-{incident_id}",
        )

    # =========================================================================
    # 4. Retain Successful Fix
    # =========================================================================

    def retain_successful_fix(
        self,
        incident_id: str,
        service: str,
        action_type: str,
        parameters: Dict[str, Any],
        rationale: str,
        outcome_notes: str,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains verified successful remediation action for future Time Machine matches.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        content_lines = [
            f"# Successful Remediation Experience: {action_type} on {service}",
            f"**Incident ID:** {incident_id} | **Outcome:** SUCCESSFUL",
            "",
            "## Action Rationale",
            rationale,
            "",
            "## Execution Parameters",
            f"```json\n{json.dumps(parameters, indent=2)}\n```",
            "",
            "## Verified Outcome & Results",
            outcome_notes,
        ]

        content = "\n".join(content_lines)
        tags = [
            "remediation",
            "outcome:successful",
            f"action:{action_type.lower()}",
            f"service:{service.lower()}",
            f"incident:{incident_id}",
        ]
        metadata = {
            "incident_id": incident_id,
            "service": service,
            "action_type": action_type,
            "outcome": "successful",
            "type": "successful_fix",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=tags,
            metadata=metadata,
            document_id=f"remediation-success-{incident_id}-{action_type}",
        )

    # =========================================================================
    # 5. Retain Failed Fix (Failed-Fix Memory Guard)
    # =========================================================================

    def retain_failed_fix(
        self,
        incident_id: str,
        service: str,
        action_type: str,
        parameters: Dict[str, Any],
        failure_reason: str,
        unintended_consequences: Optional[str] = None,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains failed remediation attempt to warn engineers against repeating dangerous mistakes.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        content_lines = [
            f"# CRITICAL WARNING: Failed Remediation Fix for {service}",
            f"**Action Attempted:** {action_type} | **Incident:** {incident_id} | **Outcome:** FAILED",
            "",
            "## Why This Fix Failed",
            failure_reason,
            "",
            "## Parameters Used in Failed Attempt",
            f"```json\n{json.dumps(parameters, indent=2)}\n```",
        ]

        if unintended_consequences:
            content_lines.extend([
                "",
                "## Unintended Negative Consequences / Collateral Damage",
                unintended_consequences,
            ])

        content = "\n".join(content_lines)
        tags = [
            "remediation",
            "outcome:failed",
            "warning:failed_fix",
            f"action:{action_type.lower()}",
            f"service:{service.lower()}",
            f"incident:{incident_id}",
        ]
        metadata = {
            "incident_id": incident_id,
            "service": service,
            "action_type": action_type,
            "outcome": "failed",
            "type": "failed_fix",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=tags,
            metadata=metadata,
            document_id=f"remediation-failed-{incident_id}-{action_type}",
        )

    # =========================================================================
    # 6. Retain Engineer Feedback
    # =========================================================================

    def retain_engineer_feedback(
        self,
        incident_id: str,
        service: str,
        engineer_id: str,
        rating: str,
        feedback_text: str,
        tags: Optional[List[str]] = None,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains human engineer feedback and validation into organizational memory.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        content_lines = [
            f"# Senior Engineer Feedback: Incident {incident_id}",
            f"**Service:** {service} | **Engineer:** {engineer_id} | **Rating:** {rating}",
            "",
            "## Feedback & Assessment",
            feedback_text,
        ]

        content = "\n".join(content_lines)
        all_tags = [
            "feedback",
            f"rating:{rating.lower()}",
            f"service:{service.lower()}",
            f"incident:{incident_id}",
            *(tags or []),
        ]
        metadata = {
            "incident_id": incident_id,
            "service": service,
            "engineer_id": engineer_id,
            "rating": rating,
            "type": "engineer_feedback",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=all_tags,
            metadata=metadata,
            document_id=f"feedback-{incident_id}-{engineer_id}",
        )

    # =========================================================================
    # 7. Retain Postmortem
    # =========================================================================

    def retain_postmortem(
        self,
        incident_id: str,
        service: str,
        executive_summary: str,
        root_cause_analysis: str,
        lessons_learned: List[str],
        preventive_actions: List[str],
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retains full postmortem analysis and long-term preventive lessons.

        Hindsight API Method:
            - `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        content_lines = [
            f"# Complete Postmortem Analysis: Incident {incident_id}",
            f"**Service:** {service}",
            "",
            "## Executive Summary",
            executive_summary,
            "",
            "## Comprehensive Root Cause Analysis",
            root_cause_analysis,
            "",
            "## Lessons Learned",
        ]
        for lesson in lessons_learned:
            content_lines.append(f"- {lesson}")

        content_lines.extend(["", "## Preventive Action Items"])
        for action in preventive_actions:
            content_lines.append(f"- {action}")

        content = "\n".join(content_lines)
        tags = [
            "postmortem",
            "lessons_learned",
            f"service:{service.lower()}",
            f"incident:{incident_id}",
        ]
        metadata = {
            "incident_id": incident_id,
            "service": service,
            "type": "postmortem",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return self._execute_retain(
            bank_id=target_bank,
            content=content,
            tags=tags,
            metadata=metadata,
            document_id=f"postmortem-{incident_id}",
        )

    # =========================================================================
    # 8. Recall Similar Incidents
    # =========================================================================

    def recall_similar_incidents(
        self,
        query: str,
        service: Optional[str] = None,
        limit: int = 5,
        bank_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recalls historically similar incidents using semantic & temporal retrieval.

        Hindsight API Method:
            - `Hindsight.recall(bank_id=..., query=..., tags=..., tags_match='any', max_tokens=...)`
        """
        target_bank = bank_id or self.bank_id
        tags = ["incident"]
        if service:
            tags.append(f"service:{service.lower()}")

        search_query = query if not service else f"{service} {query}"
        return self._execute_recall(
            bank_id=target_bank,
            query=search_query,
            tags=tags,
            tags_match="any",
            limit=limit,
        )

    # =========================================================================
    # 9. Recall Failed Remediations
    # =========================================================================

    def recall_failed_remediations(
        self,
        service: Optional[str] = None,
        action_type: Optional[str] = None,
        query: Optional[str] = None,
        bank_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recalls past failed remediations for the Incident Time Machine and safety guards.

        Hindsight API Method:
            - `Hindsight.recall(bank_id=..., query=..., tags=..., tags_match='any', max_tokens=...)`
        """
        target_bank = bank_id or self.bank_id
        tags = ["warning:failed_fix", "outcome:failed"]
        if service:
            tags.append(f"service:{service.lower()}")
        if action_type:
            tags.append(f"action:{action_type.lower()}")

        query_parts = ["failed remediation fix disastrous mistake warning"]
        if service:
            query_parts.append(service)
        if action_type:
            query_parts.append(action_type)
        if query:
            query_parts.append(query)

        search_query = " ".join(query_parts)
        return self._execute_recall(
            bank_id=target_bank,
            query=search_query,
            tags=tags,
            tags_match="any",
            limit=10,
        )

    # =========================================================================
    # 10. Recall Successful Remediations
    # =========================================================================

    def recall_successful_remediations(
        self,
        service: Optional[str] = None,
        action_type: Optional[str] = None,
        query: Optional[str] = None,
        bank_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Recalls historically verified successful remediation actions.

        Hindsight API Method:
            - `Hindsight.recall(bank_id=..., query=..., tags=..., tags_match='any', max_tokens=...)`
        """
        target_bank = bank_id or self.bank_id
        tags = ["outcome:successful", "remediation"]
        if service:
            tags.append(f"service:{service.lower()}")
        if action_type:
            tags.append(f"action:{action_type.lower()}")

        query_parts = ["successful remediation fix verified resolution"]
        if service:
            query_parts.append(service)
        if action_type:
            query_parts.append(action_type)
        if query:
            query_parts.append(query)

        search_query = " ".join(query_parts)
        return self._execute_recall(
            bank_id=target_bank,
            query=search_query,
            tags=tags,
            tags_match="any",
            limit=10,
        )

    # =========================================================================
    # 11. Reflect on Incident History
    # =========================================================================

    def reflect_on_incident_history(
        self,
        query: str,
        context: Optional[str] = None,
        service: Optional[str] = None,
        bank_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates a synthesized organizational mental model reflection across historical incidents.

        Hindsight API Method:
            - `Hindsight.reflect(bank_id=..., query=..., context=..., tags=...)`
        """
        target_bank = bank_id or self.bank_id
        client = self.get_client()
        if not client:
            return {
                "success": False,
                "text": "Hindsight client is unavailable; reflection skipped.",
                "based_on": [],
                "error": "Client not initialized",
            }

        tags = [f"service:{service.lower()}"] if service else None

        try:
            logger.info("Executing Hindsight reflect query", extra={"bank_id": target_bank, "query": query})
            reflect_resp = client.reflect(
                bank_id=target_bank,
                query=query,
                context=context,
                budget="mid",
                tags=tags,
                tags_match="any" if tags else None,
                include_facts=True,
            )

            response_text = getattr(reflect_resp, "text", "")
            based_on_items = []
            if hasattr(reflect_resp, "based_on") and reflect_resp.based_on:
                for item in reflect_resp.based_on:
                    if hasattr(item, "to_dict"):
                        based_on_items.append(item.to_dict())
                    elif isinstance(item, dict):
                        based_on_items.append(item)
                    else:
                        based_on_items.append(str(item))

            return {
                "success": True,
                "text": response_text,
                "based_on": based_on_items,
                "usage": getattr(reflect_resp, "usage", None),
            }
        except ApiException as api_err:
            logger.error("ApiException during Hindsight reflect", extra={"error": str(api_err), "bank_id": target_bank})
            return {
                "success": False,
                "text": f"Hindsight reflection error: {api_err}",
                "based_on": [],
                "error": str(api_err),
            }
        except Exception as exc:
            logger.error("Error during Hindsight reflect", extra={"error": str(exc), "bank_id": target_bank}, exc_info=True)
            return {
                "success": False,
                "text": f"Hindsight reflection failed: {exc}",
                "based_on": [],
                "error": str(exc),
            }

    # =========================================================================
    # Internal Retain and Recall Executors with Graceful Failure & Retries
    # =========================================================================

    def _execute_retain(
        self,
        bank_id: str,
        content: str,
        tags: List[str],
        metadata: Dict[str, str],
        document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal helper to execute Hindsight retain with safety and structured logging."""
        client = self.get_client()
        if not client:
            logger.warning("Hindsight client unavailable; skipping retain", extra={"tags": tags, "doc": document_id})
            return {"success": False, "error": "Client not initialized", "bank_id": bank_id}

        try:
            logger.info("Retaining memory to Hindsight", extra={"bank_id": bank_id, "tags": tags, "doc": document_id})
            resp = client.retain(
                bank_id=bank_id,
                content=content,
                tags=tags,
                metadata=metadata,
                document_id=document_id,
            )
            return {
                "success": getattr(resp, "success", True),
                "bank_id": getattr(resp, "bank_id", bank_id),
                "items_count": getattr(resp, "items_count", 1),
                "operation_id": getattr(resp, "operation_id", None),
            }
        except ApiException as api_err:
            logger.error(
                "ApiException during Hindsight retain",
                extra={"error": str(api_err), "bank_id": bank_id, "doc": document_id},
            )
            return {"success": False, "error": str(api_err), "bank_id": bank_id}
        except Exception as exc:
            logger.error(
                "Error executing Hindsight retain",
                extra={"error": str(exc), "bank_id": bank_id, "doc": document_id},
                exc_info=True,
            )
            return {"success": False, "error": str(exc), "bank_id": bank_id}

    def _execute_recall(
        self,
        bank_id: str,
        query: str,
        tags: Optional[List[str]] = None,
        tags_match: str = "any",
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Internal helper to execute Hindsight recall with safety, parsing results gracefully."""
        client = self.get_client()
        if not client:
            logger.warning("Hindsight client unavailable; skipping recall", extra={"query": query})
            return []

        try:
            logger.info("Executing Hindsight recall", extra={"bank_id": bank_id, "query": query, "tags": tags})
            resp = client.recall(
                bank_id=bank_id,
                query=query,
                tags=tags,
                tags_match=tags_match,  # type: ignore
                max_tokens=4096,
                budget="mid",
            )

            results: List[Dict[str, Any]] = []
            raw_results = getattr(resp, "results", []) or []

            for item in raw_results[:limit]:
                result_dict = {
                    "id": getattr(item, "id", None),
                    "text": getattr(item, "text", ""),
                    "type": getattr(item, "type", "memory"),
                    "tags": getattr(item, "tags", []) or [],
                    "metadata": getattr(item, "metadata", {}) or {},
                    "context": getattr(item, "context", None),
                    "score": getattr(getattr(item, "scores", None), "combined_score", None),
                }
                results.append(result_dict)

            return results
        except ApiException as api_err:
            logger.error("ApiException during Hindsight recall", extra={"error": str(api_err), "query": query})
            return []
        except Exception as exc:
            logger.error("Error executing Hindsight recall", extra={"error": str(exc), "query": query}, exc_info=True)
            return []


# Global singleton instance of HindsightService
hindsight_service = HindsightService()
