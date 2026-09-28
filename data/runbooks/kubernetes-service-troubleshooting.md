# Kubernetes Service Troubleshooting

## Overview
Kubernetes service incidents often appear as unavailable endpoints or rapid restarts. The most valuable signal is whether the service is failing readiness, crashing, or being overwhelmed by dependency latency.

## Service diagnostics
- Check deployment rollout state and pod restarts.
- Confirm readiness probes are succeeding.
- Inspect container logs for crash loops or unhandled exceptions.
- Verify whether the service is overloaded by upstream queue latency.

## Recovery flow
1. Verify that the service has healthy replicas and no restart loop.
2. Check if the request queue is growing faster than the application can drain it.
3. If the problem is dependency-driven, stop adding more replicas until the blocking dependency is addressed.
4. Apply the smallest safe intervention to reduce load or isolate the bad dependency.
5. Recheck readiness and traffic before reopening canaries.

## Guardrails
- Do not restart all pods when the service is blocked on a downstream dependency.
- Prefer a single, targeted rollback or configuration revert over broad churn.
- Maintain an explicit canary window for hotfix and deployment changes.
