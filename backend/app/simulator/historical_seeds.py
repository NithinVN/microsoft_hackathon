from typing import Any, Dict, List, Optional

HISTORICAL_SEEDS: List[Dict[str, Any]] = [
  {
    "hindsight_incident_id": "INC-419",
    "title": "PostgreSQL Thundering Herd & Cascading Connection Lock",
    "service": "payment-processor",
    "occurrence_date": "2025-11-14",
    "severity": "SEV-1",
    "root_cause": "Under sudden promotional burst traffic, connection pool reached 100% capacity. On-call engineer rebooted the primary PostgreSQL stateful pod without draining connections, triggering a massive 10,000-client simultaneous reconnect thundering herd that locked all database CPU cores for 45 minutes.",
    "symptoms": [
      "P99 latency spiked from 180ms to 4200ms",
      "PgBouncer pool saturation 100/100",
      "HTTP 504 Gateway Timeout rate at 38%",
    ],
    "attempted_fixes": [
      {
        "action": "Restart PostgreSQL Primary Stateful Pod",
        "outcome": "FAILURE",
        "consequence": "Catastrophic cascade failure: 30 client service pods simultaneously hammered the database upon reboot, keeping CPU at 100% and extending outage by 45 minutes.",
        "engineer_notes": "NEVER RESTART THE DB IN FLIGHT UNDER SURGE! It makes the outage 10x worse.",
      },
      {
        "action": "Scale PgBouncer Pool Ceiling to 250 & Terminate Idle Leaked Connections",
        "outcome": "SUCCESS",
        "consequence": "Resolved query backlog in 3 minutes with zero lost transactions.",
        "engineer_notes": "Cleanly drained the backlog. Recovery was instantaneous.",
      },
    ],
    "hindsight_reflection": "Organizational Experience Rule: For database connection starvation, restarting the cluster induces cascade thundering herd. Always resize pool and terminate idle sessions via PgBouncer first.",
    "tags": ["database", "postgres", "pgbouncer", "connection-pool", "thundering-herd"],
  },
  {
    "hindsight_incident_id": "INC-382",
    "title": "Redis Cache Invalidation & Cold Cache Stampede",
    "service": "catalog-service",
    "occurrence_date": "2025-08-11",
    "severity": "SEV-2",
    "root_cause": "Synchronized midnight TTL expiry across catalog items triggered a cold cache stampede to the read-replica database. An engineer executed FLUSHALL in an attempt to clear stale keys, destroying remaining warm keys.",
    "symptoms": [
      "Redis hit ratio plummeted from 98% to 11%",
      "Read replica DB query volume spiked 9x",
      "Catalog page render latency > 3500ms",
    ],
    "attempted_fixes": [
      {
        "action": "Execute FLUSHALL on Redis cluster",
        "outcome": "FAILURE",
        "consequence": "Completely wiped remaining warm cache, crashing the primary read replica under 100% cache miss storm.",
        "engineer_notes": "FLUSHALL was catastrophic. Never flush the cache during an ongoing stampede.",
      },
      {
        "action": "Execute Automated Top-1000 SKU Cache Pre-Warming & Enable Jitter",
        "outcome": "SUCCESS",
        "consequence": "Restored hit ratio to 96% within 4 minutes and stabilized read replica CPU to 22%.",
        "engineer_notes": "Prewarming top products stopped the dogpile immediately.",
      },
    ],
    "hindsight_reflection": "Organizational Experience Rule: Do NOT flush Redis during a stampede. Run staggered key warm-up and enable circuit breaker jitter.",
    "tags": ["redis", "cache", "stampede", "catalog", "dogpiling"],
  },
  {
    "hindsight_incident_id": "INC-502",
    "title": "Billing Worker Memory Leak & OOM Killer Cascade",
    "service": "billing-worker",
    "occurrence_date": "2025-10-03",
    "severity": "SEV-2",
    "root_cause": "Unbounded caching of PDF invoices in worker memory heap caused continuous OOMKilled exit code 137 every 12 minutes. An engineer scaled up the replica count from 4 to 12, which merely multiplied total cluster memory pressure.",
    "symptoms": [
      "Worker pods repeatedly restarting with ExitCode 137 (OOMKilled)",
      "Billing queue processing delay exceeded 45 minutes",
      "Node memory pressure alerts firing",
    ],
    "attempted_fixes": [
      {
        "action": "Scale Worker Replica Count from 4 to 12",
        "outcome": "FAILURE",
        "consequence": "Accelerated node memory depletion, causing Kubernetes kubelet to evict unrelated critical services.",
        "engineer_notes": "Scaling up leaked pods makes cluster exhaustion faster. Fix the batch size instead.",
      },
      {
        "action": "Restart Worker Deployment with Batch Size Capped at 50 & Force Garbage Collection",
        "outcome": "SUCCESS",
        "consequence": "Memory flattened at 420MB per pod; queue drained to 0 in 10 minutes.",
        "engineer_notes": "Applying batch limit stopped the leak until permanent release was prepared.",
      },
    ],
    "hindsight_reflection": "Organizational Experience Rule: For memory leaks, scaling pod replicas multiplies cluster memory starvation. Apply batch processing constraints and perform a staged rolling restart.",
    "tags": ["memory-leak", "oom", "billing", "worker", "kubernetes"],
  },
  {
    "hindsight_incident_id": "INC-612",
    "title": "Corrupt Release Config & Auth Interceptor Crash",
    "service": "auth-service",
    "occurrence_date": "2026-01-19",
    "severity": "SEV-1",
    "root_cause": "Deployment v2.14.0 contained a missing environment variable in the JWT validation interceptor, throwing NullPointerException on 100% of user authentication requests.",
    "symptoms": [
      "HTTP 500 Internal Server Error rate spiked to 92% on /api/v1/auth/login",
      "Deployment v2.14.0 completed 4 minutes prior to alert",
      "Stack trace indicates NullPointerException in JwtAuthFilter.java",
    ],
    "attempted_fixes": [
      {
        "action": "Attempt Hot-Patch Config in Live Container",
        "outcome": "FAILURE",
        "consequence": "Container config drifted from GitOps state, resulting in inconsistent node behaviors and partial 500s.",
        "engineer_notes": "In-place hot patching breaks infrastructure-as-code and caused config drift.",
      },
      {
        "action": "Execute Immediate Rollback to Previous Stable Release v2.13.9",
        "outcome": "SUCCESS",
        "consequence": "Full traffic restored to 100% success rate in 90 seconds.",
        "engineer_notes": "Clean rollback is always faster and safer than trying to debug broken deployments in flight.",
      },
    ],
    "hindsight_reflection": "Organizational Experience Rule: When an incident starts within 15 minutes of a deployment and error rate is > 50%, rollback to previous green release immediately. Never attempt live hot-patching.",
    "tags": ["deployment", "auth", "rollback", "null-pointer", "config-error"],
  },
]


def get_historical_seeds() -> List[Dict[str, Any]]:
    """Returns the list of seed historical incident records for Hindsight."""
    return HISTORICAL_SEEDS


def get_historical_match_for_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Finds corresponding historical seed for a given scenario."""
    mapping = {
        "database_connection_pool": "INC-419",
        "payment_api_latency": "INC-419",
        "dependency_service_failure": "INC-382",
        "memory_leak": "INC-502",
        "failed_deployment": "INC-612",
    }
    match_id = mapping.get(scenario_id)
    if not match_id:
        return None
    for seed in HISTORICAL_SEEDS:
        if seed["hindsight_incident_id"] == match_id:
            return seed
    return None
