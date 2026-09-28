# API Latency Troubleshooting

## Overview
API latency issues are often caused by dependency slowness, worker starvation, or queue growth. The key is to determine whether the bottleneck is in the app itself or in an upstream dependency.

## Investigation sequence
1. Confirm the service latency and p99 distribution for the failing API.
2. Determine whether the latency aligns with downstream dependency degradation.
3. Inspect thread utilization and queue backlog for the app service.
4. Compare active requests against worker capacity and dependency timeout thresholds.

## Common response patterns
- External API latency is the root cause when all outbound HTTP requests are slow and the service thread pool saturates.
- Internal queue backlog indicates an app-level bottleneck or misconfiguration.
- Gateways may show elevated 5xx errors when upstream dependency latency overwhelms request handling.

## Safeguards
- Add client-side timeout limits and circuit breakers for outbound dependencies.
- Fail fast rather than allowing request threads to pile up.
- Avoid scaling without first understanding whether the bottleneck is upstream or internal.
