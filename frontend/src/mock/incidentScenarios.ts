import { IncidentScenario } from '../types/incident';

export const MOCK_SCENARIOS: IncidentScenario[] = [
  {
    id: 'INC-7041',
    title: 'PostgreSQL Connection Pool Starvation in Payment Gateway',
    severity: 'SEV-1',
    service: 'payment-processor',
    environment: 'production-us-east',
    status: 'DETECTED',
    startedAt: '2026-09-28T12:15:30Z',
    summary: 'Payment service connection pool saturated at 100/100 connections. P99 latency spiked from 180ms to 4200ms with a 38% HTTP 504 Gateway Timeout rate on checkout requests.',
    
    currentEvidence: {
      telemetrySummary: 'Active DB pool saturation: 100/100. Waiting queries queue: 342. Host CPU: 64%, Memory: 71%.',
      metrics: {
        cpuUsage: [
          { timestamp: '12:10', value: 34, label: '34%' },
          { timestamp: '12:12', value: 38, label: '38%' },
          { timestamp: '12:14', value: 52, label: '52%' },
          { timestamp: '12:16', value: 68, label: '68%' },
          { timestamp: '12:18', value: 74, label: '74%' },
          { timestamp: '12:20', value: 71, label: '71%' },
        ],
        errorRate: [
          { timestamp: '12:10', value: 0.1, label: '0.1%' },
          { timestamp: '12:12', value: 0.4, label: '0.4%' },
          { timestamp: '12:14', value: 6.2, label: '6.2%' },
          { timestamp: '12:16', value: 24.5, label: '24.5%' },
          { timestamp: '12:18', value: 38.2, label: '38.2%' },
          { timestamp: '12:20', value: 36.8, label: '36.8%' },
        ],
        latencyMs: [
          { timestamp: '12:10', value: 160, label: '160ms' },
          { timestamp: '12:12', value: 195, label: '195ms' },
          { timestamp: '12:14', value: 850, label: '850ms' },
          { timestamp: '12:16', value: 2400, label: '2400ms' },
          { timestamp: '12:18', value: 4200, label: '4200ms' },
          { timestamp: '12:20', value: 3950, label: '3950ms' },
        ],
      },
      liveLogs: [
        '[12:14:02 ERROR] [pg-pool] TimeoutError: ResourceRequest timed out after 5000ms (max_connections=100 reached)',
        '[12:14:05 WARN] [checkout-api] Circuit breaker open for downstream: postgres-primary.prod.internal:5432',
        '[12:14:12 ERROR] [payment-processor] Failed to acquire transaction lock for authorization: connection lease expired',
        '[12:15:20 FATAL] [http-worker-4] HTTP 504 Gateway Timeout generated on POST /api/v1/payments/charge',
      ],
      traces: [
        {
          traceId: 'tr-9982-f41a',
          rootService: 'api-gateway',
          failingSpan: 'postgres.acquire_connection',
          durationMs: 5002,
          httpStatus: 504,
        },
        {
          traceId: 'tr-9982-f42b',
          rootService: 'checkout-frontend',
          failingSpan: 'payment-processor.authorize',
          durationMs: 5120,
          httpStatus: 504,
        },
      ],
    },

    historicalEvidence: [
      {
        hindsightIncidentId: 'INC-419',
        title: 'PostgreSQL Thundering Herd & Cascading Failure',
        occurrenceDate: '2025-11-14',
        similarityScore: 0.94,
        pastRootCause: 'Under sudden promotional traffic, connection pool exhausted. On-call engineer restarted the PostgreSQL primary node without draining connections, causing a thundering herd reconnect storm that locked all database cores.',
        attemptedFixes: [
          {
            action: 'Restart PostgreSQL Primary Node',
            outcome: 'FAILURE',
            consequence: 'Cascading lock failure; downtime extended by 45 minutes.',
            engineerNotes: 'DO NOT RESTART THE DB IN FLIGHT! 10,000 clients simultaneously reconnecting hammered CPU to 100%.',
          },
          {
            action: 'Scale PgBouncer Pool Size to 250 & Terminate Idle Leaked Connections',
            outcome: 'SUCCESS',
            consequence: 'Resolved queue in 3 minutes without drop in active transactions.',
            engineerNotes: 'Cleanly drained the backlog. Recovery was instantaneous.',
          },
        ],
        hindsightReflection: 'Organizational Memory Warning: For connection pool starvation, restarting the cluster induces cascade thundering herd. Always resize pool and terminate idle connections via PgBouncer first.',
      },
      {
        hindsightIncidentId: 'INC-288',
        title: 'Payment Gateway DB Connection Leak',
        occurrenceDate: '2025-06-22',
        similarityScore: 0.81,
        pastRootCause: 'Unclosed SQLAlchemy session inside async retry loop caused slow leak of connections.',
        attemptedFixes: [
          {
            action: 'Kill Idle Transactions > 60s via PgAdmin',
            outcome: 'SUCCESS',
            consequence: 'Freed 42 idle connections immediately.',
            engineerNotes: 'Bought 30 minutes of headroom while hotfix deployment rolled out.',
          },
        ],
        hindsightReflection: 'Idle connection killing is a safe, zero-downtime relief valve before scaling pool size.',
      },
    ],

    documentation: [
      {
        runbookTitle: 'Payment Gateway Database Operational Runbook',
        docUrl: 'https://runbooks.corp.internal/payments/postgres-troubleshooting',
        matchedSection: 'Section 4.2: Handling Connection Pool Saturation',
        snippet: 'If pool saturation exceeds 95%, inspect pg_stat_activity for idle-in-transaction sessions. Never execute a hard reboot of the primary replica while under load.',
        lastUpdated: '2026-01-10',
      },
      {
        runbookTitle: 'PgBouncer Dynamic Configuration Guide',
        docUrl: 'https://runbooks.corp.internal/infra/pgbouncer-dynamic-scaling',
        matchedSection: 'Dynamic Pool Allocation without Process Restart',
        snippet: 'Run "PAUSE db" -> "RELOAD" -> "RESUME db" with max_client_conn increased. Total latency penalty < 200ms.',
        lastUpdated: '2025-09-18',
      },
    ],

    aiInference: {
      confidence: 0.96,
      rootCauseHypothesis: 'Payment processor connection pool (limit=100) has been depleted by 42 idle-in-transaction connections combined with a 15% traffic surge. Queries are blocking on connection lease.',
      chainOfThought: [
        '1. Current metrics confirm DB host CPU is only 71%, eliminating CPU bottleneck as root cause.',
        '2. Live logs explicitly state ResourceRequest timed out waiting for connection (100/100 reached).',
        '3. Hindsight memory recall (INC-419, similarity 0.94) warns strongly against database restart due to past catastrophic thundering herd outcome.',
        '4. Hindsight historical records confirm scaling PgBouncer pool to 250 and killing idle connections resolved INC-419 in 3 minutes.',
        '5. Runbook section 4.2 corroborates idle transaction clearance as pre-approved standard operation.',
      ],
      recommendedFixId: 'FIX-A',
      riskAssessment: 'Low Risk for pool resize + idle termination; Catastrophic Risk for cluster restart.',
    },

    blastRadius: {
      rootService: 'payment-processor',
      affectedServicesCount: 4,
      estimatedUserImpactPct: 38,
      tier1Impact: true,
      nodes: [
        { id: '1', name: 'api-gateway', status: 'DEGRADED', type: 'GATEWAY', latency: '4200ms', errorRate: '38%', affected: true },
        { id: '2', name: 'checkout-frontend', status: 'DEGRADED', type: 'SERVICE', latency: '4300ms', errorRate: '38%', affected: true },
        { id: '3', name: 'payment-processor', status: 'OUTAGE', type: 'SERVICE', latency: '5000ms', errorRate: '82%', affected: true },
        { id: '4', name: 'postgres-primary', status: 'DEGRADED', type: 'DATABASE', latency: '210ms', errorRate: '12%', affected: true },
        { id: '5', name: 'order-fulfillment', status: 'HEALTHY', type: 'SERVICE', latency: '45ms', errorRate: '0%', affected: false },
        { id: '6', name: 'notification-service', status: 'HEALTHY', type: 'SERVICE', latency: '32ms', errorRate: '0%', affected: false },
      ],
      links: [
        { source: 'checkout-frontend', target: 'api-gateway', trafficRps: 450, healthy: false },
        { source: 'api-gateway', target: 'payment-processor', trafficRps: 320, healthy: false },
        { source: 'payment-processor', target: 'postgres-primary', trafficRps: 320, healthy: false },
        { source: 'api-gateway', target: 'order-fulfillment', trafficRps: 180, healthy: true },
        { source: 'order-fulfillment', target: 'notification-service', trafficRps: 180, healthy: true },
      ],
    },

    candidates: [
      {
        id: 'FIX-A',
        actionName: 'Expand PgBouncer Pool to 250 & Terminate Idle Leaked Connections',
        description: 'Dynamically reconfigure PgBouncer connection ceiling and execute pre-approved pg_terminate_backend for sessions idle > 60s.',
        commandPreview: 'pgbouncer_ctl reload --max-clients 250 && sql_clean_idle_transactions(idle_sec=60)',
        safetyLevel: 'SAFE',
        historicalPrecedent: 'SUCCESS_BEFORE',
        historicalContext: 'Successfully restored operations in INC-419 within 3 minutes with zero dropped active queries.',
        predictedImpact: 'Immediate recovery of connection queue; drop in P99 latency from 4200ms to < 200ms.',
        isRecommended: true,
      },
      {
        id: 'FIX-B',
        actionName: 'Restart PostgreSQL Primary Cluster Pod',
        description: 'Hard reboot of the primary database pod to purge all connections.',
        commandPreview: 'kubectl rollout restart statefulset/postgres-primary -n database',
        safetyLevel: 'HIGH_RISK',
        historicalPrecedent: 'FAILED_BEFORE',
        historicalContext: 'FAILED catastrophically in INC-419: triggered 45m thundering herd downtime. Hindsight warns: DO NOT ATTEMPT.',
        predictedImpact: 'Severe outage extension due to simultaneous reconnect storm from 30+ service pods.',
        isRecommended: false,
      },
      {
        id: 'FIX-C',
        actionName: 'Throttle Inbound Checkout Traffic by 50%',
        description: 'Apply rate-limiting on API Gateway checkout route to shed load.',
        commandPreview: 'gateway_ctl apply-ratelimit --route /api/v1/payments --drop 50',
        safetyLevel: 'MEDIUM_RISK',
        historicalPrecedent: 'UNTESTED',
        historicalContext: 'Protects database but causes intentional 50% business checkout failure.',
        predictedImpact: 'Relieves database stress but rejects ~160 legitimate customer payments per minute.',
        isRecommended: false,
      },
    ],

    failedFixWarning: {
      dangerousAction: 'Restart PostgreSQL Primary Cluster Pod (FIX-B)',
      incidentRef: 'INC-419 (2025-11-14)',
      reason: 'Failed-Fix Memory Guard: Past attempt caused catastrophic thundering herd reconnect storm.',
      historicalConsequence: 'Extended downtime by 45 minutes and corrupted 14 inflight checkout states.',
    },

    postmortem: {
      incidentId: 'INC-7041',
      title: 'PostgreSQL Connection Pool Starvation in Payment Gateway',
      durationMinutes: 14,
      severity: 'SEV-1',
      rootCause: 'Connection starvation caused by surge traffic combined with unreleased idle-in-transaction connections.',
      detectionSource: 'IncidentMind Autonomous Telemetry Observer',
      timeline: [
        { time: '12:15:30', event: 'Incident detected via 504 Gateway Timeout anomaly' },
        { time: '12:16:10', event: 'Investigation Agent collected traces and identified DB pool 100/100 saturation' },
        { time: '12:16:45', event: 'Hindsight Memory Agent retrieved INC-419 and raised Failed-Fix Warning on DB restart' },
        { time: '12:17:30', event: 'Remediation Agent formulated FIX-A (Pool resize + idle clean)' },
        { time: '12:18:15', event: 'Human approval granted by Lead SRE' },
        { time: '12:19:00', event: 'Remediation executed: PgBouncer resized to 250, 42 idle connections terminated' },
        { time: '12:20:10', event: 'Verification Agent confirmed error rate dropped to 0.05% and P99 latency returned to 175ms' },
      ],
      correctiveActions: [
        'Apply permanent PgBouncer connection pooling threshold to 300 in Helm charts',
        'Patch payment-processor SQLAlchemy session teardown decorator to prevent connection leaks',
        'Add Prometheus alert for pg_stat_activity idle_in_transaction count > 10',
      ],
      engineerFeedback: 'The Hindsight Failed-Fix warning prevented a junior on-call engineer from restarting the DB node, averting another INC-419 disaster. Outstanding organizational memory value.',
      engineerRating: 5,
      retainedToHindsight: false,
      hindsightMemoryId: 'MEM-ORG-8821',
    },
  },
  {
    id: 'INC-7042',
    title: 'Redis Invalidation Cache Stampede on Catalog Service',
    severity: 'SEV-2',
    service: 'catalog-service',
    environment: 'production-eu-west',
    status: 'DETECTED',
    startedAt: '2026-09-28T12:30:00Z',
    summary: 'Mass simultaneous key expiration triggered cache stampede. Read latency on catalog API rose to 3800ms.',
    
    currentEvidence: {
      telemetrySummary: 'Redis hit ratio plummeted from 98.4% to 11.2%. Read replica DB queries spiked 9x.',
      metrics: {
        cpuUsage: [
          { timestamp: '12:25', value: 22, label: '22%' },
          { timestamp: '12:28', value: 25, label: '25%' },
          { timestamp: '12:30', value: 89, label: '89%' },
          { timestamp: '12:32', value: 96, label: '96%' },
        ],
        errorRate: [
          { timestamp: '12:25', value: 0.0, label: '0.0%' },
          { timestamp: '12:28', value: 0.1, label: '0.1%' },
          { timestamp: '12:30', value: 8.5, label: '8.5%' },
          { timestamp: '12:32', value: 19.2, label: '19.2%' },
        ],
        latencyMs: [
          { timestamp: '12:25', value: 45, label: '45ms' },
          { timestamp: '12:28', value: 50, label: '50ms' },
          { timestamp: '12:30', value: 1800, label: '1800ms' },
          { timestamp: '12:32', value: 3800, label: '3800ms' },
        ],
      },
      liveLogs: [
        '[12:30:12 WARN] [redis-cluster] Cache miss spike: 890 misses/sec on key prefix catalog:item:*',
        '[12:30:18 ERROR] [catalog-db-read] Max pool waiting clients exceeded on postgres-read-replica-1',
      ],
      traces: [
        { traceId: 'tr-cat-101', rootService: 'catalog-service', failingSpan: 'redis.mget', durationMs: 3820, httpStatus: 504 },
      ],
    },

    historicalEvidence: [
      {
        hindsightIncidentId: 'INC-382',
        title: 'Redis Cache Flush Outage',
        occurrenceDate: '2025-08-11',
        similarityScore: 0.88,
        pastRootCause: 'Cache stampede occurred. An engineer executed FLUSHALL, wiping all remaining warm keys.',
        attemptedFixes: [
          {
            action: 'Execute FLUSHALL to reset cache state',
            outcome: 'FAILURE',
            consequence: 'Completely destroyed warm cache, crashing the primary read database.',
            engineerNotes: 'FLUSHALL was disastrous. Never flush the cache during a stampede.',
          },
          {
            action: 'Enable probabilistic early expiration jitter & execute warm-up script',
            outcome: 'SUCCESS',
            consequence: 'Hit ratio restored to 95% in 4 minutes.',
            engineerNotes: 'Warming top 1000 SKU keys stopped the database thrashing immediately.',
          },
        ],
        hindsightReflection: 'Do NOT flush Redis during a stampede. Run staggered key warm-up and enable circuit breaker jitter.',
      },
    ],

    documentation: [
      {
        runbookTitle: 'Catalog Cache Disaster Recovery',
        docUrl: 'https://runbooks.corp.internal/catalog/cache-stampede',
        matchedSection: 'Section 2.1: Key Jitter and Cache Warming',
        snippet: 'To mitigate dogpiling, activate probabilistic early recomputation and invoke cache_warmup_top_skus(count=1000).',
        lastUpdated: '2026-02-01',
      },
    ],

    aiInference: {
      confidence: 0.93,
      rootCauseHypothesis: 'Synchronized TTL expiration on popular catalog items created dogpiling on the underlying read database.',
      chainOfThought: [
        '1. Cache hit ratio dropped to 11.2% while traffic volume is within normal bounds.',
        '2. Read replica DB CPU jumped to 96% due to un-cached queries.',
        '3. Hindsight memory INC-382 explicitly warns FLUSHALL triggers read replica crash.',
        '4. Recommended action is key warming and staggered jitter.',
      ],
      recommendedFixId: 'FIX-CAT-A',
      riskAssessment: 'High Risk for FLUSHALL; Safe for Top-SKU Cache Prewarming.',
    },

    blastRadius: {
      rootService: 'catalog-service',
      affectedServicesCount: 3,
      estimatedUserImpactPct: 24,
      tier1Impact: false,
      nodes: [
        { id: '1', name: 'api-gateway', status: 'DEGRADED', type: 'GATEWAY', latency: '3800ms', errorRate: '19%', affected: true },
        { id: '2', name: 'catalog-service', status: 'OUTAGE', type: 'SERVICE', latency: '3900ms', errorRate: '22%', affected: true },
        { id: '3', name: 'redis-cache', status: 'DEGRADED', type: 'CACHE', latency: '120ms', errorRate: '5%', affected: true },
        { id: '4', name: 'catalog-db-read', status: 'DEGRADED', type: 'DATABASE', latency: '450ms', errorRate: '8%', affected: true },
      ],
      links: [
        { source: 'api-gateway', target: 'catalog-service', trafficRps: 800, healthy: false },
        { source: 'catalog-service', target: 'redis-cache', trafficRps: 800, healthy: false },
        { source: 'catalog-service', target: 'catalog-db-read', trafficRps: 600, healthy: false },
      ],
    },

    candidates: [
      {
        id: 'FIX-CAT-A',
        actionName: 'Execute Automated Top-SKU Cache Pre-Warming & Enable Jitter',
        description: 'Runs pre-approved warming script on top 1000 catalog items with randomized TTL jitter (±15%).',
        commandPreview: 'python -m runbooks.catalog_warmup --top 1000 --jitter 15',
        safetyLevel: 'SAFE',
        historicalPrecedent: 'SUCCESS_BEFORE',
        historicalContext: 'Resolved INC-382 in 4 minutes without database overload.',
        predictedImpact: 'Restores cache hit ratio to > 90% and cuts read latency to < 60ms.',
        isRecommended: true,
      },
      {
        id: 'FIX-CAT-B',
        actionName: 'Flush Redis Cluster to Clear Corrupt Keys',
        description: 'Execute FLUSHALL on Redis cluster nodes.',
        commandPreview: 'redis-cli -c FLUSHALL ASYNC',
        safetyLevel: 'HIGH_RISK',
        historicalPrecedent: 'FAILED_BEFORE',
        historicalContext: 'FAILED in INC-382: crashed the read replica DB under 100% cache miss storm.',
        predictedImpact: 'Guaranteed total catalog outage.',
        isRecommended: false,
      },
    ],

    failedFixWarning: {
      dangerousAction: 'Flush Redis Cluster to Clear Corrupt Keys (FIX-CAT-B)',
      incidentRef: 'INC-382 (2025-08-11)',
      reason: 'Failed-Fix Memory Guard: Running FLUSHALL during stampede multiplies database load by 10x.',
      historicalConsequence: 'Completely toppled the primary read replica in past outage.',
    },

    postmortem: {
      incidentId: 'INC-7042',
      title: 'Redis Invalidation Cache Stampede on Catalog Service',
      durationMinutes: 8,
      severity: 'SEV-2',
      rootCause: 'Synchronized midnight TTL expiry created mass cache miss cascade.',
      detectionSource: 'Cache Hit Ratio Telemetry Monitor',
      timeline: [
        { time: '12:30:00', event: 'Cache hit ratio dropped below 15% alert threshold' },
        { time: '12:31:00', event: 'Hindsight recalled INC-382: warned against FLUSHALL' },
        { time: '12:32:00', event: 'Approved Top-SKU Pre-Warming script' },
        { time: '12:34:00', event: 'Warmup completed: hit ratio back to 96%' },
      ],
      correctiveActions: [
        'Enforce mandatory jitter on all Redis cache expiration keys',
        'Add rate-limiter in front of database fallback path',
      ],
      engineerFeedback: 'Immediate recognition of the stampede prevented an accidental FLUSHALL. Great safety guardrail.',
      engineerRating: 5,
      retainedToHindsight: false,
      hindsightMemoryId: 'MEM-ORG-8822',
    },
  },
];
