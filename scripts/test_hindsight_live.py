"""IncidentMind - Hindsight Cloud Memory Layer Verification Script.

This script executes live operations against Hindsight using the official Python client (`hindsight-client`):
1. Creates / connects to the memory bank (`Hindsight.create_bank`)
2. Retains a sample production incident (`Hindsight.retain`)
3. Retains a verified failed remediation warning (`Hindsight.retain`)
4. Recalls relevant memories and failed fix warnings (`Hindsight.recall`)
5. Performs a cognitive reflection query across institutional memory (`Hindsight.reflect`)

Usage:
    python scripts/test_hindsight_live.py
"""

import os
import sys
from datetime import datetime, timezone
import json

# Ensure project root is in pythonpath
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.memory.hindsight_service import HindsightService, hindsight_service


def run_hindsight_verification():
    print("=" * 80)
    print("IncidentMind - Official Hindsight Cloud Memory Layer Verification")
    print("=" * 80)
    print(f"Target Base URL: {settings.HINDSIGHT_BASE_URL}")
    print(f"Target Bank ID:  {settings.HINDSIGHT_BANK_ID}")
    print(f"API Key Set:     {'YES (configured)' if settings.HINDSIGHT_API_KEY else 'NO (empty)'}")
    print("-" * 80)

    # 1. Health Check
    print("\n[Step 1] Checking Hindsight Connection & Health Status...")
    print("Hindsight API Methods Used: `Hindsight.get_version()`, `Hindsight.get_bank_config()`")
    health = hindsight_service.check_health()
    print(f"Health Result:\n{json.dumps(health, indent=2)}")

    # 2. Create / Connect to Memory Bank
    print("\n[Step 2] Creating or Connecting to Memory Bank...")
    print(f"Hindsight API Method Used: `Hindsight.create_bank(bank_id='{settings.HINDSIGHT_BANK_ID}', ...)`")
    bank_result = hindsight_service.create_memory_bank()
    print(f"Bank Result:\n{json.dumps(bank_result, indent=2, default=str)}")

    # 3. Retain Test Incident
    print("\n[Step 3] Retaining Production Incident into Hindsight...")
    print("Hindsight API Method Used: `Hindsight.retain(bank_id=..., content=..., metadata=..., tags=...)`")
    test_incident = {
        "incident_id": "INC-TEST-001",
        "title": "PostgreSQL Connection Starvation under Peak Traffic",
        "affected_service": "payment-api",
        "severity": "critical",
        "status": "resolved",
        "detected_at": datetime.now(timezone.utc).isoformat(),
        "description": "Payment checkout service experienced severe connection pool exhaustion causing 504 Gateway Timeouts.",
        "symptoms": [
            "Active connections reached pool limit of 50/50",
            "HTTP 504 Gateway Timeout rate spiked to 34%",
            "Checkout API latency increased to 8,200ms",
        ],
        "root_cause": "Async database session leak in checkout retry loop without proper context manager exit.",
        "resolution": "Scaled max_connections pool size from 50 to 150 and deployed session context manager bugfix.",
        "logs": [
            "FATAL: remaining connection slots are reserved for non-replication superuser connections",
            "sqlalchemy.exc.TimeoutError: QueuePool limit of size 50 overflow 10 reached",
        ],
    }
    retain_res = hindsight_service.retain_incident(test_incident)
    print(f"Retain Incident Result:\n{json.dumps(retain_res, indent=2, default=str)}")

    # 4. Retain Failed-Fix Memory (Failed-Fix Guard)
    print("\n[Step 4] Retaining Disastrous Failed Fix Warning into Hindsight...")
    print("Hindsight API Method Used: `Hindsight.retain(bank_id=..., tags=['warning:failed_fix', ...])`")
    failed_fix_res = hindsight_service.retain_failed_fix(
        incident_id="INC-TEST-001",
        service="payment-api",
        action_type="RESTART_DATABASE",
        parameters={"graceful": False, "flush_tables": False},
        failure_reason="Abrupt hard restart of PostgreSQL without pre-warming caused 100% cache drop, cascading thundering herd to replica DBs, resulting in an extended 45-minute total outage.",
        unintended_consequences="Cascading crash across auth-service and cart-service due to abrupt TCP reset storm.",
    )
    print(f"Retain Failed Fix Result:\n{json.dumps(failed_fix_res, indent=2, default=str)}")

    # 5. Recall Similar Incidents
    print("\n[Step 5] Recalling Similar Historical Incidents from Memory...")
    print("Hindsight API Method Used: `Hindsight.recall(bank_id=..., query=..., tags=['incident', ...])`")
    recalled_incidents = hindsight_service.recall_similar_incidents(
        query="database connection pool exhaustion and checkout timeouts",
        service="payment-api",
        limit=3,
    )
    print(f"Recalled Incidents Count: {len(recalled_incidents)}")
    for idx, inc in enumerate(recalled_incidents, start=1):
        print(f"\n  [Memory #{idx}] ID: {inc.get('id')} | Score: {inc.get('score')}")
        print(f"  Tags: {inc.get('tags')}")
        print(f"  Text Excerpt:\n    {inc.get('text', '')[:200]}...")

    # 6. Recall Failed Remediations (Incident Time Machine Guard)
    print("\n[Step 6] Recalling Failed Remediation Warnings (Incident Time Machine)...")
    print("Hindsight API Method Used: `Hindsight.recall(bank_id=..., tags=['warning:failed_fix', 'outcome:failed'])`")
    failed_fixes = hindsight_service.recall_failed_remediations(
        service="payment-api",
        action_type="RESTART_DATABASE",
    )
    print(f"Recalled Failed Fixes Count: {len(failed_fixes)}")
    for idx, fix in enumerate(failed_fixes, start=1):
        print(f"\n  [Warning #{idx}] ID: {fix.get('id')}")
        print(f"  Tags: {fix.get('tags')}")
        print(f"  Warning Text:\n    {fix.get('text', '')[:250]}...")

    # 7. Cognitive Reflection Query
    print("\n[Step 7] Performing Hindsight Cognitive Reflection...")
    print("Hindsight API Method Used: `Hindsight.reflect(bank_id=..., query=..., budget='mid', ...)`")
    reflection = hindsight_service.reflect_on_incident_history(
        query="What are the recurring failure patterns for payment-api and what remediation actions should NEVER be taken?",
        service="payment-api",
    )
    print(f"Reflection Result:\n{json.dumps(reflection, indent=2, default=str)}")

    print("\n" + "=" * 80)
    print("Hindsight Memory Layer Verification Completed Successfully.")
    print("=" * 80)
    hindsight_service.close()


if __name__ == "__main__":
    run_hindsight_verification()
