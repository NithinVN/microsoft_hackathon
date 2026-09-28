# Dependency Failure Procedures

## Overview
Dependency failures often create user-visible symptoms even when the primary service appears healthy. The key is to determine whether the dependency is failing, saturating, or returning invalid responses.

## Investigation flow
1. Check whether the dependency is returning errors or timing out.
2. Confirm whether the primary service is blocking threads while waiting for the dependency.
3. Review the service dependency graph and determine what downstream capabilities are impacted.
4. Apply timeouts, circuit breaking, or queueing before escalating.

## Safe controls
- Fail fast to external calls rather than letting threads pile up.
- Use async retry queues for non-critical operations downstream.
- Confirm upstream provider health before attempting service-side scale changes.
- Document which dependencies are customer-impacting and which are background-only.
