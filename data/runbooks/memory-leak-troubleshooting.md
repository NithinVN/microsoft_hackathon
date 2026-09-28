# Memory Leak Troubleshooting

## Overview
Memory leaks usually show up as steadily rising heap usage, slower GC activity, and eventual saturation. The mitigation should focus on confirming leak behavior before forcing a restart.

## Diagnostic checks
- Review heap growth over time and garbage collection pressure.
- Check for repeated object retention in request or cache paths.
- Inspect whether a recently deployed change created a retention cycle.

## Remediation flow
1. Confirm the service is not leaking memory due to an external dependency or cyclic cache.
2. If the process is stable but the heap is not reclaiming, cap or reset the offending cache.
3. Only restart if a controlled drain or reconfiguration fails.
4. Verify the service returns to stable memory usage before re-enabling full traffic.

## Caution
- Avoid broad cache invalidations during active user traffic unless the change is approved and scoped.
- A restart is not a diagnosis; it is only a recovery action after evidence is collected.
