# PostgreSQL Connection Pool Troubleshooting

## Overview
The PostgreSQL connection pool is often the first bottleneck during high-traffic event bursts. Symptoms include 504 responses, queue growth, and repeated database connection refusal errors. The first action is to confirm active connections, max_connections, and idle connection churn before increasing capacity.

## Symptoms and triage
- Active connections are pinned near or at the configured connection limit.
- New backend clients receive "FATAL: sorry, too many clients already" errors.
- Checkout or API requests time out while the database is still partially healthy.
- Idle sessions remain open and continue to consume pool headroom.

## Recovery steps
1. Measure active_connections and max_connections for the primary database.
2. Identify any stuck or idle sessions that are not closing properly.
3. Reap idle sessions and drain unnecessary connections before increasing limits.
4. If traffic is still above baseline, raise max_connections only after headroom is confirmed.
5. Review application retry loops and ensure they do not create unbounded sessions.

## Avoidance and prevention
- Configure a short idle timeout for application sessions.
- Avoid hard restarts under traffic spikes because they can trigger a thundering herd.
- Add connection pool diagnostics in the application health checks.
- Confirm capacity settings before high-volume campaigns or promotional events.
