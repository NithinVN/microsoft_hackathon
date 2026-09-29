import { MOCK_SCENARIOS } from './incidentScenarios';
import type { IncidentScenario } from '../types/incident';
import type { OrganizationalMemoryResult, HindsightMemoryRecord } from '../api/client';

export const DEMO_INCIDENT_ID = 'INC-DEMO-001';
export const SECOND_DEMO_INCIDENT_ID = 'INC-DEMO-002';

/**
 * Side-by-side diagnosis inputs are intentionally identical. Hindsight evidence
 * below is transcribed from data/historical_incidents.json (INC-H101), not a
 * generated similarity score or claimed production retrieval result.
 */
export const HINDSIGHT_AB_COMPARISON = {
  incident: {
    service: 'payment-api',
    symptoms: ['37% error rate', '18 second p99 latency', '98% PostgreSQL connection utilization'],
    context: 'Release v2.8.4 deployed six minutes before the incident symptoms intensified.',
    evidence: [
      'Current telemetry: 37% errors, 18 second p99 latency, 98% connection utilization.',
      'Current logs: PostgreSQL connection acquisition timeouts and expired leases.',
      'Deployment record: payment-api v2.8.4 at 09:24 UTC.',
    ],
  },
  withoutMemory: {
    diagnosis: 'Database connection saturation is a plausible cause based on current utilization and connection timeout signals. Validate pool configuration and the recent deployment.',
    recommendations: ['Inspect pool configuration and deployment changes; validate capacity before choosing a remediation.'],
    historicalMatches: [] as string[],
    failedFixWarnings: [] as string[],
    lessons: [] as string[],
    evidenceRefs: ['current metrics', 'current logs', 'deployment record'],
  },
  withHindsight: {
    diagnosis: 'The current signals are consistent with the connection-pool exhaustion recorded in INC-H101. The historical record supports pool correction; it does not establish that this incident has the same cause.',
    recommendations: ['Prefer SCALE_CONNECTION_POOL with idle-connection reclamation; validate against the live pool guardrails.'],
    historicalMatches: ['INC-H101 · PostgreSQL Connection Pool Exhaustion under Flash Sale Surge'],
    failedFixWarnings: ['RESTART_DATABASE failed in INC-H101: abrupt resets caused a thundering-herd crash. Avoid a hard restart under load.'],
    lessons: [
      'Engineer feedback (sre_alex, 5_stars): increasing the pool limit and reaping idle connections resolved the incident; do not restart the primary database under load.',
      'Postmortem: tune max_connections and idle timeouts in the pooler; hard restarts during traffic spikes require connection draining.',
    ],
    successfulFixes: ['SCALE_CONNECTION_POOL succeeded in INC-H101: capacity increased from 100 to 300 and abandoned idle connections were reclaimed.'],
    evidenceRefs: ['current metrics', 'current logs', 'deployment record', 'INC-H101', 'INC-H101/root_cause', 'INC-H101/actions_attempted', 'INC-H101/engineer_feedback', 'INC-H101/lessons_learned'],
    source: 'Seeded organizational history · data/historical_incidents.json · INC-H101',
  },
} as const;

export const DEMO_STEPS = [
  { title: 'Open incident simulator', detail: 'Start the deterministic Payment API scenario; no cloud alert provider is required.' },
  { title: 'Trigger Payment API failure', detail: 'Open INC-DEMO-001 with 37% errors, 18 second latency, and 98% database utilization.' },
  { title: 'Investigate metrics', detail: 'Current telemetry shows 37% errors, p99 latency of 18 seconds, and 98% database pool utilization.' },
  { title: 'Inspect logs', detail: 'Connection acquisition timeouts and pool saturation appear in payment logs.' },
  { title: 'Inspect recent deployment', detail: 'The deterministic deployment record shows v2.8.4 six minutes before the alert.' },
  { title: 'Calculate blast radius', detail: 'Payment API, checkout, and the database path are degraded; 37% of requests are affected.' },
  { title: 'Recall Hindsight incidents', detail: 'Search the seeded organizational-memory records for connection-pool incidents.' },
  { title: 'Find failed remediation', detail: 'INC-419 records a failed hard restart that caused a reconnect storm.' },
  { title: 'Find successful remediation', detail: 'INC-419 records pool scaling and idle-session cleanup as successful.' },
  { title: 'Diagnose with evidence', detail: 'Agent inference: likely connection-pool exhaustion, supported by current telemetry and history.' },
  { title: 'Review evidence sources', detail: 'Separate current signals, Hindsight history, runbook guidance, and agent inference.' },
  { title: 'Run Incident Time Machine', detail: 'Replay candidate fixes against historical outcomes.' },
  { title: 'Compare remediation actions', detail: 'Compare pool correction and database restart using historical outcomes and current runbook guidance.' },
  { title: 'Recommend pool correction', detail: 'Recommend pool correction; the historical restart failure is a visible guardrail.' },
  { title: 'Request human approval', detail: 'No remediation runs until an engineer approves the proposed action.' },
  { title: 'Execute simulated remediation', detail: 'Apply the vetted pool correction in simulation mode only.' },
  { title: 'Show simulated recovery', detail: 'Scripted metrics trend toward normal; these are demo values, not live measurements.' },
  { title: 'Mark demo incident resolved', detail: 'The local scenario advances to resolved after simulated verification.' },
  { title: 'Generate postmortem', detail: 'Capture cause, impact, timeline, remediation, and preventive actions.' },
  { title: 'Retain outcome and lessons', detail: 'Attempt Hindsight Cloud retain when configured; otherwise keep the local demo lesson visible.' },
  { title: 'Trigger a second similar incident', detail: 'Open INC-DEMO-002 with the same connection-saturation signature.' },
  { title: 'Recall and avoid the failed fix', detail: 'Show the first incident’s retained lesson and block the previously failed database restart.' },
] as const;

export function createPaymentApiDemoScenario(recovered = false, resolved = false, retained = false, postmortemReady = false, secondIncident = false): IncidentScenario {
  const scenario = JSON.parse(JSON.stringify(MOCK_SCENARIOS[0])) as IncidentScenario;
  scenario.id = secondIncident ? SECOND_DEMO_INCIDENT_ID : DEMO_INCIDENT_ID;
  scenario.title = secondIncident ? 'Payment API connection saturation recurrence' : 'Payment API connection pool exhaustion after deployment';
  scenario.service = 'payment-api';
  scenario.startedAt = '2026-09-29T09:30:00Z';
  scenario.status = resolved ? 'RESOLVED' : 'DETECTED';
  scenario.summary = secondIncident
    ? 'Similar Payment API failure recurred. Hindsight recalls INC-DEMO-001’s outcome: avoid a database restart and use the pool correction playbook.'
    : recovered
    ? 'Simulated recovery verified: error rate is 0.4%, p99 latency is 220ms, and database connection utilization is 52%.'
    : 'Payment API is returning 37% errors with 18 second latency and 98% database connection utilization after deployment v2.8.4.';
  scenario.currentEvidence.telemetrySummary = !secondIncident && recovered
    ? 'Error rate 0.4%; p99 latency 220ms; PostgreSQL connection utilization 52/100 after simulated pool correction.'
    : 'Error rate 37%; p99 latency 18 seconds; PostgreSQL connection utilization 98/100. Deployment v2.8.4 completed at 09:24 UTC.';
  scenario.currentEvidence.metrics.errorRate = !secondIncident && recovered
    ? [37, 21, 4.2, 0.8, 0.4].map((value, index) => ({ timestamp: `09:${32 + index * 2}`, value, label: `${value}%` }))
    : [0.2, 1.4, 12, 29, 37].map((value, index) => ({ timestamp: `09:${24 + index * 2}`, value, label: `${value}%` }));
  scenario.currentEvidence.metrics.latencyMs = !secondIncident && recovered
    ? [18000, 8100, 1200, 500, 220].map((value, index) => ({ timestamp: `09:${32 + index * 2}`, value, label: value >= 1000 ? `${value / 1000}s` : `${value}ms` }))
    : [220, 900, 4200, 12000, 18000].map((value, index) => ({ timestamp: `09:${24 + index * 2}`, value, label: value >= 1000 ? `${value / 1000}s` : `${value}ms` }));
  scenario.currentEvidence.liveLogs = [
    '[09:29:42 ERROR] [pg-pool] Timed out acquiring a connection (98/100 connections in use)',
    '[09:29:45 ERROR] [payment-api] Database connection lease expired while authorizing payment',
    '[09:29:51 WARN] [checkout] Requests queueing behind saturated payment database pool',
    '[09:30:00 INFO] [release-controller] payment-api v2.8.4 deployed at 09:24 UTC',
  ];
  scenario.aiInference.confidence = 0;
  scenario.aiInference.rootCauseHypothesis = 'Likely database connection pool exhaustion after deployment v2.8.4; 98% utilization, connection acquisition timeouts, and the six-minute deployment correlation support this diagnosis.';
  scenario.aiInference.chainOfThought = [
    'Current metrics: 37% errors, 18 second p99 latency, and 98% database connection utilization.',
    'Payment logs show connection acquisition timeouts and expired connection leases.',
    'Release v2.8.4 completed six minutes before the incident symptoms intensified.',
    'Seeded Hindsight memory INC-419 records a hard restart failure and reconnect storm.',
    'The same historical record reports success after pool correction and idle connection cleanup.',
  ];
  scenario.blastRadius.estimatedUserImpactPct = 37;
  scenario.blastRadius.rootService = 'payment-api';
  scenario.blastRadius.nodes = scenario.blastRadius.nodes.map((node) => ({
    ...node,
    name: node.name === 'payment-processor' ? 'payment-api' : node.name,
    errorRate: node.affected ? '37%' : '0%',
    latency: node.affected ? '18s' : node.latency,
  }));
  scenario.candidates[0] = {
    ...scenario.candidates[0],
    actionName: 'Correct database connection pool and drain idle connections',
    description: 'Apply the vetted pool configuration correction, then drain only idle connections.',
    historicalContext: 'Hindsight seed INC-419 reports success: pool correction cleared the queue without interrupting active transactions.',
    predictedImpact: 'Demo-only simulated values: 0.4% errors, 220ms latency, and 52% pool utilization.',
  };
  scenario.candidates[1] = {
    ...scenario.candidates[1],
    actionName: 'Hard restart the database',
    description: 'A hard database restart previously triggered a reconnect storm under load; the Time Machine flags this action as failed.',
    commandPreview: 'BLOCKED BY HISTORICAL FAILED-FIX EVIDENCE · SIMULATION ONLY',
    historicalContext: 'Hindsight seed INC-419 reports failure: database restart triggered a reconnect storm and prolonged the outage.',
  };
  scenario.postmortem = {
    ...scenario.postmortem,
    incidentId: scenario.id,
    title: 'Payment API connection pool exhaustion after deployment',
    durationMinutes: resolved ? 6 : 0,
    rootCause: 'Database connection pool exhaustion following deployment v2.8.4.',
    timeline: postmortemReady ? [
      { time: '09:30', event: 'Incident detected: error rate 37%, p99 latency 18s, pool utilization 98%.' },
      { time: '09:31', event: 'Logs and deployment v2.8.4 correlated with connection acquisition timeouts.' },
      { time: '09:32', event: 'Hindsight INC-419 warned against restart and supported pool correction.' },
      { time: '09:33', event: 'Engineer approved simulated database pool correction.' },
      { time: '09:34', event: 'Verification passed: error rate 0.4%, p99 220ms, pool utilization 52%.' },
    ] : [],
    retainedToHindsight: retained,
    hindsightMemoryId: retained ? 'INC-DEMO-001' : undefined,
    correctiveActions: [
      'Alert when payment database pool utilization exceeds 90%.',
      'Verify connection pool settings as part of deployment v2.8.4 checks.',
      'Keep service restart behind historical failed-fix and human approval safeguards.',
    ],
  };
  if (secondIncident) {
    scenario.status = 'DETECTED';
    scenario.summary = 'A second deterministic incident shows the same 37% error rate, 18 second latency, and 98% connection utilization. The Memory Used panel carries forward the first incident’s lesson.';
    scenario.currentEvidence.liveLogs = [
      '[10:02:11 ERROR] [pg-pool] Timed out acquiring a connection (98/100 connections in use)',
      '[10:02:14 ERROR] [payment-api] Connection lease expired during payment authorization',
      '[10:02:19 WARN] [checkout] Requests queueing behind the saturated database pool',
      '[10:02:22 INFO] [incident-agent] Hindsight lesson loaded: do not hard restart the database under load',
    ];
    scenario.postmortem.durationMinutes = 0;
    scenario.postmortem.timeline = [];
  }
  return scenario;
}

function memoryRecord(id: string, category: string, text: string, type: string, incidentId = 'INC-419'): HindsightMemoryRecord {
  return {
    id, category, text, type, tags: ['payment-api', 'demo', category], source: 'Hindsight demo memory',
    metadata: { incident_id: incidentId, service: 'payment-api', outcome: type }, score: null,
  };
}

export function createPaymentApiDemoMemory(retained = false, secondIncident = false): OrganizationalMemoryResult {
  const historical = memoryRecord('INC-419', 'historical_incidents', 'Database connection pool saturation caused payment failures after a traffic surge.', 'historical_incident');
  const failed = memoryRecord('FIX-INC-419-RESTART', 'failed_fixes', 'Restart service failed: it triggered a reconnect storm and prolonged the outage by 45 minutes.', 'failed_fix');
  const successful = memoryRecord('FIX-INC-419-POOL', 'successful_fixes', 'Correcting pool capacity and draining idle connections restored service without dropping active transactions.', 'successful_fix');
  const rootCause = memoryRecord('CAUSE-INC-419-POOL', 'root_causes', 'Database connection pool exhaustion caused connection acquisition timeouts.', 'root_cause');
  const feedback = memoryRecord('FEEDBACK-INC-419', 'engineer_feedback', 'Never restart the database under load. Increasing pool headroom and reaping idle connections resolved the incident.', 'engineer_feedback');
  const lessons = retained ? [memoryRecord('LESSON-INC-DEMO-001', 'postmortem_lessons', 'For saturated payment database pools, prefer a pool correction over restarting the service; correlate deployment timing and verify recovery metrics.', 'postmortem_lesson', 'INC-DEMO-001')] : [];
  const categories = {
    historical_incidents: [historical],
    root_causes: [rootCause],
    successful_fixes: [successful],
    failed_fixes: [failed],
    engineer_feedback: [feedback],
    postmortem_lessons: lessons,
  };
  const retrieved = [historical, rootCause, failed, successful, feedback, ...lessons];
  return {
    current_incident: { incident_id: secondIncident ? SECOND_DEMO_INCIDENT_ID : DEMO_INCIDENT_ID, service: 'payment-api', query: secondIncident ? 'Second similar incident: 37% errors, 18s latency, 98% connection utilization; use previous outcome and avoid the failed restart.' : '37% errors 18s latency 98% database connection utilization following deployment v2.8.4' },
    status: 'available', bank_id: 'incidentmind-demo-bank',
    health: { healthy: true, status: 'demo-fixture', message: 'Deterministic demo memory; no external alert provider required.' },
    categories, retrieved_memories: retrieved, agent_evidence: retrieved,
  };
}
