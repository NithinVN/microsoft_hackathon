from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from backend.app.schemas.simulator import ScenarioInfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


SCENARIO_CATALOG: Dict[str, Dict[str, Any]] = {
    "database_connection_pool": {
        "id": "database_connection_pool",
        "name": "Database Connection Pool Exhaustion",
        "description": "Payment service connection pool saturated at 100/100 connections. P99 latency spiked to 4200ms with 38% HTTP 504 Gateway Timeouts.",
        "default_severity": "SEV-1",
        "primary_service": "payment-processor",
        "affected_services": ["api-gateway", "checkout-frontend", "payment-processor", "postgres-primary"],
        "root_cause_type": "Connection Starvation",
        "symptoms": [
            "Active DB pool saturation: 100/100 (100%)",
            "HTTP 504 Gateway Timeout rate on /api/v1/payments/charge: 38.2%",
            "P99 latency elevated from 180ms to 4200ms",
            "Waiting queries queue depth: 342",
        ],
        "alert": {
            "alert_id": "ALT-PG-POOL-001",
            "name": "PostgreSQLConnectionPoolExhausted",
            "source": "Prometheus/Alertmanager",
            "severity": "critical",
            "status": "firing",
            "payload": {
                "metric": "pgbouncer_pools_client_waiting_connections",
                "threshold": 10,
                "current_value": 342,
                "host": "postgres-primary.prod.internal:5432",
            },
        },
        "service_info": {
            "name": "payment-processor",
            "tier": 1,
            "owner_team": "payments-sre",
            "repository_url": "https://github.com/org/payment-processor",
            "health_status": "OUTAGE",
            "metadata_json": {"language": "python", "framework": "fastapi", "db_pool": "pgbouncer"},
        },
        "deployment_info": {
            "version": "v1.18.2",
            "environment": "production-us-east",
            "status": "SUCCESS",
            "deployed_by": "release-engineer",
            "commit_hash": "c83b91a7df02",
        },
        "metrics": {
            "cpu_usage_pct": [34, 38, 52, 68, 74, 71],
            "error_rate_pct": [0.1, 0.4, 6.2, 24.5, 38.2, 36.8],
            "p99_latency_ms": [160, 195, 850, 2400, 4200, 3950],
            "pool_saturation_pct": [40, 55, 85, 100, 100, 100],
        },
        "live_logs": [
            "[ERROR] [pg-pool] TimeoutError: ResourceRequest timed out after 5000ms (max_connections=100 reached)",
            "[WARN] [checkout-api] Circuit breaker open for downstream: postgres-primary.prod.internal:5432",
            "[ERROR] [payment-processor] Failed to acquire transaction lock for authorization: connection lease expired",
            "[FATAL] [http-worker-4] HTTP 504 Gateway Timeout generated on POST /api/v1/payments/charge",
        ],
        "traces": [
            {
                "trace_id": "tr-9982-f41a",
                "root_service": "api-gateway",
                "failing_span": "postgres.acquire_connection",
                "duration_ms": 5002,
                "http_status": 504,
            },
            {
                "trace_id": "tr-9982-f42b",
                "root_service": "checkout-frontend",
                "failing_span": "payment-processor.authorize",
                "duration_ms": 5120,
                "http_status": 504,
            },
        ],
        "suggested_hindsight_incident": "INC-419",
    },
    "payment_api_latency": {
        "id": "payment_api_latency",
        "name": "Payment API Latency Spike & Gateway Degradation",
        "description": "Third-party payment settlement API experiencing elevated latency. Checkout authorization P99 latency rose to 6800ms with 45% failure rate.",
        "default_severity": "SEV-1",
        "primary_service": "payment-processor",
        "affected_services": ["checkout-frontend", "payment-processor", "third-party-stripe-gw"],
        "root_cause_type": "Upstream Dependency Timeout",
        "symptoms": [
            "P99 checkout authorization latency: 6800ms",
            "Third-party payment gateway HTTP timeout rate: 45.1%",
            "Inbound payment authorization queue delay > 90 seconds",
        ],
        "alert": {
            "alert_id": "ALT-PAY-LAT-002",
            "name": "PaymentGatewayDownstreamLatencySpike",
            "source": "Azure Monitor",
            "severity": "critical",
            "status": "firing",
            "payload": {
                "metric": "payment_authorization_duration_seconds",
                "threshold": 3.0,
                "current_value": 6.8,
                "downstream_partner": "stripe-api-gateway",
            },
        },
        "service_info": {
            "name": "payment-processor",
            "tier": 1,
            "owner_team": "payments-sre",
            "repository_url": "https://github.com/org/payment-processor",
            "health_status": "DEGRADED",
            "metadata_json": {"partner_routing": "stripe_primary_adyen_secondary"},
        },
        "deployment_info": {
            "version": "v1.18.2",
            "environment": "production-us-east",
            "status": "SUCCESS",
            "deployed_by": "release-engineer",
            "commit_hash": "c83b91a7df02",
        },
        "metrics": {
            "cpu_usage_pct": [28, 30, 42, 45, 48, 46],
            "error_rate_pct": [0.2, 1.2, 14.0, 32.5, 45.1, 42.0],
            "p99_latency_ms": [210, 340, 1800, 4900, 6800, 6500],
            "gateway_timeout_pct": [0, 0, 12, 35, 45, 43],
        },
        "live_logs": [
            "[ERROR] [stripe-client] ReadTimeout: HTTPSConnectionPool(host='api.stripe.com', port=443): Read timed out after 6000ms",
            "[WARN] [payment-processor] Secondary fallback gateway (Adyen) circuit breaker not engaged due to manual toggle lock",
            "[ERROR] [checkout-api] Client dropped connection waiting for payment auth after 8000ms",
        ],
        "traces": [
            {
                "trace_id": "tr-pay-771a",
                "root_service": "checkout-frontend",
                "failing_span": "stripe.charge.create",
                "duration_ms": 6120,
                "http_status": 504,
            }
        ],
        "suggested_hindsight_incident": "INC-419",
    },
    "memory_leak": {
        "id": "memory_leak",
        "name": "Billing Worker Memory Leak & OOM Throttling",
        "description": "Billing batch worker pod memory continuously climbs to 98% heap, triggering Kubernetes OOMKilled exit code 137 every 12 minutes.",
        "default_severity": "SEV-2",
        "primary_service": "billing-worker",
        "affected_services": ["billing-worker", "invoice-generation-queue"],
        "root_cause_type": "Memory Leak / Unbounded Buffer",
        "symptoms": [
            "Worker pod restarts: 6 within last 1 hour",
            "Pod exit status: ExitCode 137 (OOMKilled)",
            "Billing queue backlog exceeds 45,000 pending jobs",
        ],
        "alert": {
            "alert_id": "ALT-OOM-WORKER-003",
            "name": "ContainerOOMKilledAlert",
            "source": "Prometheus/KubernetesObserver",
            "severity": "major",
            "status": "firing",
            "payload": {
                "container": "billing-worker",
                "memory_limit_bytes": 2147483648,
                "exit_code": 137,
                "restart_count": 6,
            },
        },
        "service_info": {
            "name": "billing-worker",
            "tier": 2,
            "owner_team": "billing-core",
            "repository_url": "https://github.com/org/billing-worker",
            "health_status": "DEGRADED",
            "metadata_json": {"runtime": "jvm", "heap_max": "2048m"},
        },
        "deployment_info": {
            "version": "v3.4.1",
            "environment": "production-us-east",
            "status": "SUCCESS",
            "deployed_by": "ci-automation",
            "commit_hash": "f94a2b109e31",
        },
        "metrics": {
            "cpu_usage_pct": [45, 60, 78, 92, 98, 15],
            "error_rate_pct": [0.0, 2.0, 8.5, 22.0, 35.0, 0.0],
            "memory_usage_pct": [50, 68, 84, 94, 98, 42],
            "queue_lag_count": [1200, 4500, 18000, 32000, 45000, 46000],
        },
        "live_logs": [
            "[FATAL] [jvm] java.lang.OutOfMemoryError: Java heap space during PDF render batch",
            "[WARN] [k8s-kubelet] Container billing-worker exceeded memory limit (2048Mi) -> sending SIGKILL (ExitCode 137)",
            "[ERROR] [job-consumer] Worker thread died unexpectedly. Requeuing 250 unacknowledged invoice tasks.",
        ],
        "traces": [
            {
                "trace_id": "tr-oom-881a",
                "root_service": "billing-worker",
                "failing_span": "pdf.render_invoice_batch",
                "duration_ms": 14200,
                "http_status": 500,
            }
        ],
        "suggested_hindsight_incident": "INC-502",
    },
    "failed_deployment": {
        "id": "failed_deployment",
        "name": "Failed Deployment & Auth Interceptor Crash",
        "description": "Release v2.14.0 deployed 5 minutes ago introduced a configuration bug. 94% of authentication requests are throwing NullPointerException.",
        "default_severity": "SEV-1",
        "primary_service": "auth-service",
        "affected_services": ["api-gateway", "auth-service", "user-web-frontend"],
        "root_cause_type": "Bad Configuration / Release Defect",
        "symptoms": [
            "HTTP 500 Internal Server Error rate: 94.2% on /api/v1/auth/login",
            "Deployment v2.14.0 completed 5 minutes prior to first alert",
            "Stack trace indicates NullPointerException in JwtAuthInterceptor.java",
        ],
        "alert": {
            "alert_id": "ALT-AUTH-5XX-004",
            "name": "AuthServiceHttp5xxSpike",
            "source": "Prometheus/Alertmanager",
            "severity": "critical",
            "status": "firing",
            "payload": {
                "http_5xx_rate": 0.942,
                "deployment_version": "v2.14.0",
                "service": "auth-service",
            },
        },
        "service_info": {
            "name": "auth-service",
            "tier": 1,
            "owner_team": "security-identity",
            "repository_url": "https://github.com/org/auth-service",
            "health_status": "OUTAGE",
            "metadata_json": {"language": "java", "auth_protocol": "oauth2_jwt"},
        },
        "deployment_info": {
            "version": "v2.14.0",
            "environment": "production-us-east",
            "status": "FAILED",
            "deployed_by": "cd-bot-automation",
            "commit_hash": "a9f4c12bb092",
        },
        "metrics": {
            "cpu_usage_pct": [22, 24, 25, 26, 25, 24],
            "error_rate_pct": [0.05, 0.1, 75.0, 94.2, 94.0, 93.8],
            "p99_latency_ms": [45, 50, 110, 120, 115, 118],
            "successful_logins_per_min": [2400, 2450, 150, 22, 18, 20],
        },
        "live_logs": [
            "[ERROR] [auth-filter] java.lang.NullPointerException: Cannot invoke 'String.getBytes()' because 'jwtSecretKey' is null",
            "[ERROR] [auth-service] Unhandled exception in SecurityFilterChain on POST /api/v1/auth/login: NullPointerException",
            "[FATAL] [api-gateway] Downstream auth-service returning 500 for all bearer token validation requests",
        ],
        "traces": [
            {
                "trace_id": "tr-auth-901a",
                "root_service": "api-gateway",
                "failing_span": "auth.validate_jwt",
                "duration_ms": 18,
                "http_status": 500,
            }
        ],
        "suggested_hindsight_incident": "INC-612",
    },
    "dependency_service_failure": {
        "id": "dependency_service_failure",
        "name": "Redis Cache Invalidation & Cold Cache Stampede",
        "description": "Mass simultaneous key expiration triggered cache stampede. Read latency on catalog API rose to 3800ms and read replica DB CPU spiked to 96%.",
        "default_severity": "SEV-2",
        "primary_service": "catalog-service",
        "affected_services": ["api-gateway", "catalog-service", "redis-cache", "postgres-read-replica"],
        "root_cause_type": "Cache Stampede / Dogpiling",
        "symptoms": [
            "Redis cache hit ratio plummeted from 98.4% to 11.2%",
            "Read replica DB query throughput spiked 9x",
            "Catalog product page render latency: 3800ms",
        ],
        "alert": {
            "alert_id": "ALT-REDIS-HIT-005",
            "name": "RedisCacheHitRatioLow",
            "source": "Prometheus/Alertmanager",
            "severity": "major",
            "status": "firing",
            "payload": {
                "metric": "redis_hit_ratio",
                "threshold": 0.85,
                "current_value": 0.112,
                "cluster": "redis-catalog-primary",
            },
        },
        "service_info": {
            "name": "catalog-service",
            "tier": 2,
            "owner_team": "catalog-team",
            "repository_url": "https://github.com/org/catalog-service",
            "health_status": "DEGRADED",
            "metadata_json": {"cache_engine": "redis", "ttl_strategy": "fixed_midnight"},
        },
        "deployment_info": {
            "version": "v4.1.0",
            "environment": "production-us-east",
            "status": "SUCCESS",
            "deployed_by": "release-engineer",
            "commit_hash": "e11d04b88a91",
        },
        "metrics": {
            "cpu_usage_pct": [22, 25, 68, 89, 96, 94],
            "error_rate_pct": [0.0, 0.1, 4.2, 12.5, 19.2, 18.0],
            "p99_latency_ms": [45, 50, 620, 1800, 3800, 3600],
            "cache_hit_ratio_pct": [98, 97, 60, 24, 11, 12],
        },
        "live_logs": [
            "[WARN] [redis-cluster] Cache miss spike: 890 misses/sec on key prefix catalog:item:*",
            "[ERROR] [catalog-db-read] Max pool waiting clients exceeded on postgres-read-replica-1",
            "[WARN] [catalog-service] Circuit breaker half-open for read replica fallback pool",
        ],
        "traces": [
            {
                "trace_id": "tr-cat-101",
                "root_service": "catalog-service",
                "failing_span": "redis.mget",
                "duration_ms": 3820,
                "http_status": 504,
            }
        ],
        "suggested_hindsight_incident": "INC-382",
    },
}


def get_all_scenarios() -> List[ScenarioInfo]:
    """List all available scenario metadata."""
    scenarios = []
    for sc in SCENARIO_CATALOG.values():
        scenarios.append(
            ScenarioInfo(
                id=sc["id"],
                name=sc["name"],
                description=sc["description"],
                default_severity=sc["default_severity"],
                primary_service=sc["primary_service"],
                affected_services=sc["affected_services"],
                root_cause_type=sc["root_cause_type"],
            )
        )
    return scenarios


def get_scenario(scenario_id: str) -> Optional[Dict[str, Any]]:
    """Get detailed scenario configuration by scenario identifier."""
    return SCENARIO_CATALOG.get(scenario_id)
