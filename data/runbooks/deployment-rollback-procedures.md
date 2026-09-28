# Deployment Rollback Procedures

## Overview
When a deployment introduces routing, configuration, or serialization regressions, rollback is often the safest recovery path. Rollbacks should occur only after confirming there is a real degradation and the last good version is known.

## Decision points
- Confirm the failed deployment introduced a config or code regression.
- Validate the rollback target is the last known good version.
- Ensure no critical migration or data migration is mid-flight.

## Rollback steps
1. Validate the deployment change against the last healthy release.
2. Trigger a controlled rollback to the previous stable version.
3. Confirm health checks and route validity are restored.
4. Keep the failing version isolated until a postmortem is complete.

## Recovery notes
- A rollback is preferred over speculative fixes when a syntax or config regression is causing 5xx errors across the edge.
- Narrow rollback windows reduce blast radius and make recovery easier to validate.
