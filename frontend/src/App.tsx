import { useEffect, useState, useCallback, useRef, type FormEvent } from 'react';
import {
  Activity,
  ArrowDown,
  ArrowRight,
  BrainCircuit,
  Clock3,
  Database,
  RefreshCw,
  HeartPulse,
  Layers3,
  MemoryStick,
  Network,
  Radar,
  ShieldCheck,
  TimerReset,
  TriangleAlert,
  Play,
  CircleCheck,
  Circle,
  PauseCircle,
} from 'lucide-react';
import { MOCK_SCENARIOS } from './mock/incidentScenarios';
import {
  createWebsiteIntegration,
  deleteWebsiteIntegration,
  fetchHealth,
  getOrganizationalMemory,
  listWebsiteIntegrations,
  retainDemoOutcome,
  scanWebsiteIntegration,
  testWebsiteIntegrationConnection,
  updateWebsiteIntegration,
  type ExternalWebsiteIntegration,
  type ExternalWebsiteScanResult,
  type ExternalWebsiteConnectionTestResult,
  HealthCheckResponse,
  OrganizationalMemoryCategory,
  OrganizationalMemoryResult,
} from './api/client';
import { createPaymentApiDemoMemory, createPaymentApiDemoScenario, DEMO_INCIDENT_ID, DEMO_STEPS, HINDSIGHT_AB_COMPARISON } from './mock/paymentApiDemo';
import type { IncidentScenario } from './types/incident';
import './App.css';

type ScreenKey =
  | 'dashboard'
  | 'activeIncident'
  | 'timeline'
  | 'memory'
  | 'hindsightAB'
  | 'diagnosis'
  | 'blastRadius'
  | 'timeMachine'
  | 'remediation'
  | 'postmortem'
  | 'learning'
  | 'externalIntegrations';

const screens: Array<{ key: ScreenKey; label: string; icon: any }> = [
  { key: 'dashboard', label: 'Dashboard', icon: Layers3 },
  { key: 'activeIncident', label: 'Active Incident', icon: Activity },
  { key: 'timeline', label: 'Incident Timeline', icon: Clock3 },
  { key: 'memory', label: 'Organizational Memory', icon: MemoryStick },
  { key: 'hindsightAB', label: 'Hindsight A/B', icon: BrainCircuit },
  { key: 'diagnosis', label: 'Diagnosis', icon: BrainCircuit },
  { key: 'blastRadius', label: 'Blast Radius', icon: Network },
  { key: 'timeMachine', label: 'Time Machine', icon: TimerReset },
  { key: 'remediation', label: 'Approval', icon: ShieldCheck },
  { key: 'postmortem', label: 'Postmortem', icon: Database },
  { key: 'learning', label: 'Learning', icon: Radar },
  { key: 'externalIntegrations', label: 'External Integrations', icon: Network },
];

type EvidenceSource = 'Current telemetry' | 'Hindsight' | 'RAG' | 'AI inference';

const evidenceSourceFor = (text: string): EvidenceSource => {
  if (/hindsight|historical|memory recall|prior incident|INC-\d+/i.test(text)) return 'Hindsight';
  if (/runbook|approved standard operation|section \d/i.test(text)) return 'RAG';
  return 'Current telemetry';
};

const sourcePill = (source: EvidenceSource) => (
  <span className={`evidence-pill evidence-pill--${source.toLowerCase().replace(/\s+/g, '-')}`}>
    {source}
  </span>
);

const severityToClass = (severity: string) => severity === 'SEV-1' ? 'severity--sev1' : severity === 'SEV-2' ? 'severity--sev2' : severity === 'SEV-3' ? 'severity--sev3' : 'severity--sev4';

const screenTitles: Record<ScreenKey, { title: string; eyebrow: string }> = {
  dashboard: { title: 'Operations overview', eyebrow: 'Command center' },
  activeIncident: { title: 'Active incident', eyebrow: 'Live response / demo scenario' },
  timeline: { title: 'Incident timeline', eyebrow: 'Response record' },
  memory: { title: 'Organizational memory', eyebrow: 'Hindsight knowledge bank' },
  hindsightAB: { title: 'Hindsight A/B demonstration', eyebrow: 'Same incident · two evidence contexts' },
  diagnosis: { title: 'Diagnosis', eyebrow: 'Evidence assessment' },
  blastRadius: { title: 'Blast radius', eyebrow: 'Service impact' },
  timeMachine: { title: 'Incident time machine', eyebrow: 'What-if analysis' },
  remediation: { title: 'Remediation approval', eyebrow: 'Human control' },
  postmortem: { title: 'Postmortem', eyebrow: 'Incident review' },
  learning: { title: 'Learning evolution', eyebrow: 'Memory lifecycle' },
  externalIntegrations: { title: 'External integrations', eyebrow: 'Website / service monitoring' },
};

const EXTERNAL_ANALYSIS_STEPS = [
  'Initialize the analysis and identify the selected integration',
  'Validate the target URL and permitted scheme',
  'Resolve and validate the target hostname',
  'Establish HTTP/HTTPS connectivity',
  'Follow and evaluate permitted redirects',
  'Record the final URL and HTTP response status',
  'Measure response time',
  'Inspect the response content type',
  'Evaluate TLS/HTTPS information when applicable',
  'Check whether a configured health endpoint exists',
  'Request the health endpoint when configured',
  'Validate and interpret the health response',
  'Identify whether a supported metrics endpoint is configured',
  'Request the metrics endpoint when configured',
  'Validate and interpret the available metrics',
  'Check API latency against documented thresholds when evidence exists',
  'Evaluate observed error rates when sufficient metrics exist',
  'Evaluate dependency health when supported evidence exists',
  'Evaluate database-pool health only when actual or explicitly simulated metrics are available',
  'Correlate the observations and determine which findings are supported',
  'Assign finding severity, confidence, impact, evidence, and recommendations',
  'Finalize the report and update the integration\'s latest scan results',
] as const;

const getStatusBadgeClass = (status: string) => {
  const normalized = status.toLowerCase();
  if (['healthy', 'connected', 'reachable', 'ok', 'success', 'available'].includes(normalized)) return 'status-badge--good';
  if (['unavailable', 'failed', 'error', 'down', 'unreachable'].includes(normalized)) return 'status-badge--error';
  return 'status-badge--neutral';
};

const memoryCategoryViews: Array<{ key: OrganizationalMemoryCategory; title: string }> = [
  { key: 'historical_incidents', title: 'Historical incidents' },
  { key: 'root_causes', title: 'Root causes' },
  { key: 'successful_fixes', title: 'Successful fixes' },
  { key: 'failed_fixes', title: 'Failed fixes' },
  { key: 'engineer_feedback', title: 'Engineer feedback' },
  { key: 'postmortem_lessons', title: 'Postmortem lessons' },
];

const learningCurveStages = [
  { incident: 'Incident 1', learning: 'Generic recommendation' },
  { incident: 'Incident 5', learning: 'Recognizes recurring database pattern' },
  { incident: 'Incident 10', learning: 'Avoids previously failed remediation' },
  { incident: 'Incident 20', learning: 'Uses accumulated organizational experience' },
];

function LearningCurve() {
  return (
    <section className="panel learning-curve-panel">
      <div className="section-header">
        <div>
          <h3>Learning curve</h3>
          <p className="muted-text">Illustrative progression, not measured incident counts or performance metrics.</p>
        </div>
      </div>
      <ol className="learning-curve">
        {learningCurveStages.map((stage) => (
          <li key={stage.incident}>
            <span className="learning-curve__incident">{stage.incident}</span>
            <span className="learning-curve__point">{stage.learning}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export function App() {
  const [activeScenario, setActiveScenario] = useState<IncidentScenario>(MOCK_SCENARIOS[0]);
  const [screen, setScreen] = useState<ScreenKey>('dashboard');
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [organizationalMemory, setOrganizationalMemory] = useState<OrganizationalMemoryResult | null>(null);
  const [loadingMemory, setLoadingMemory] = useState<boolean>(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [memoryRetry, setMemoryRetry] = useState(0);
  const [demoMode, setDemoMode] = useState(false);
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoProgress, setDemoProgress] = useState(0);
  const [demoApproved, setDemoApproved] = useState(false);
  const [demoRejected, setDemoRejected] = useState(false);
  const [demoCloudRetention, setDemoCloudRetention] = useState<'not-started' | 'pending' | 'retained' | 'unavailable'>('not-started');
  const [secondDemoIncident, setSecondDemoIncident] = useState(false);
  const emptyIntegrationForm = {
    name: '',
    baseUrl: '',
    healthUrl: '',
    serviceName: '',
    webhookUrl: '',
    serviceIdentifier: '',
    apiKey: '',
  };
  const [integrationForm, setIntegrationForm] = useState(emptyIntegrationForm);
  const [editingIntegrationId, setEditingIntegrationId] = useState<number | null>(null);
  const [integrations, setIntegrations] = useState<ExternalWebsiteIntegration[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(false);
  const [integrationError, setIntegrationError] = useState<string | null>(null);
  const [testingIntegrationId, setTestingIntegrationId] = useState<number | null>(null);
  const [scanningIntegrationId, setScanningIntegrationId] = useState<number | null>(null);
  const [scanResults, setScanResults] = useState<Record<number, ExternalWebsiteScanResult>>({});
  const [connectionResults, setConnectionResults] = useState<Record<number, ExternalWebsiteConnectionTestResult>>({});
  const [externalWorkflow, setExternalWorkflow] = useState<{
    integrationId: number;
    progress: number;
    running: boolean;
    approvalPending: boolean;
    triggerPending: boolean;
    approvalGranted: boolean;
    triggerGranted: boolean;
  } | null>(null);
  const demoMemoryRequests = useRef<Set<string>>(new Set());

  const activeCount = MOCK_SCENARIOS.filter((entry) => entry.status !== 'RESOLVED' && entry.status !== 'POSTMORTEM_SAVED').length;
  const affectedServiceCount = new Set(MOCK_SCENARIOS.flatMap((entry) => entry.blastRadius.nodes.filter((node) => node.affected).map((node) => node.name))).size;
  const latestErrorRate = activeScenario.currentEvidence.metrics.errorRate.slice(-1)[0]?.label ?? 'Unavailable';
  const latestLatency = activeScenario.currentEvidence.metrics.latencyMs.slice(-1)[0]?.label ?? 'Unavailable';
  const latestCpu = activeScenario.currentEvidence.metrics.cpuUsage.slice(-1)[0]?.label ?? 'Unavailable';

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    setHealthError(null);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err) {
      setHealthError(err instanceof Error ? err.message : 'System health could not be loaded.');
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  const loadIntegrations = useCallback(async () => {
    setIntegrationsLoading(true);
    setIntegrationError(null);
    try {
      const data = await listWebsiteIntegrations();
      setIntegrations(data);
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : 'External integrations could not be loaded.');
    } finally {
      setIntegrationsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadIntegrations();
  }, [loadIntegrations]);

  const resetIntegrationForm = () => {
    setIntegrationForm(emptyIntegrationForm);
    setEditingIntegrationId(null);
    setIntegrationError(null);
  };

  const reuseIntegration = (integration: ExternalWebsiteIntegration) => {
    setIntegrationForm({
      name: integration.name,
      baseUrl: integration.base_url,
      healthUrl: integration.health_url || '',
      serviceName: integration.service_name || '',
      webhookUrl: integration.webhook_url || '',
      serviceIdentifier: integration.service_identifier || '',
      apiKey: '',
    });
    setEditingIntegrationId(integration.id);
    setIntegrationError('Integration already exists. Edit the saved record below or update the entry to reuse it.');
  };

  const handleCreateIntegration = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = {
      name: integrationForm.name.trim(),
      base_url: integrationForm.baseUrl.trim(),
      health_url: integrationForm.healthUrl.trim() || undefined,
      service_name: integrationForm.serviceName.trim() || undefined,
      webhook_url: integrationForm.webhookUrl.trim() || undefined,
      service_identifier: integrationForm.serviceIdentifier.trim() || undefined,
      api_key: integrationForm.apiKey.trim() || undefined,
    };

    try {
      if (editingIntegrationId !== null) {
        const updated = await updateWebsiteIntegration(editingIntegrationId, payload);
        setIntegrations((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
        setConnectionResults((current) => {
          const next = { ...current };
          delete next[updated.id];
          return next;
        });
        setScanResults((current) => {
          const next = { ...current };
          delete next[updated.id];
          return next;
        });
        resetIntegrationForm();
        return;
      }

      const created = await createWebsiteIntegration(payload);
      setIntegrations((current) => [created, ...current]);
      resetIntegrationForm();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not create the website integration.';
      if (/already exists/i.test(message)) {
        const normalized = (integrationForm.name || '').trim().toLowerCase();
        const existing = integrations.find((entry) => entry.name.toLowerCase() === normalized || entry.base_url.toLowerCase() === integrationForm.baseUrl.trim().toLowerCase());
        if (existing) {
          reuseIntegration(existing);
          setIntegrationError(`Integration "${existing.name}" already exists. Reuse the existing record or edit it below.`);
          return;
        }
      }
      setIntegrationError(message);
    }
  };

  const handleTestIntegration = async (integration: ExternalWebsiteIntegration) => {
    setTestingIntegrationId(integration.id);
    try {
      const result = await testWebsiteIntegrationConnection(integration.id, {
        api_key: integrationForm.apiKey.trim() || undefined,
      });
      setConnectionResults((current) => ({ ...current, [integration.id]: result }));
      setIntegrations((current) => current.map((entry) => entry.id === integration.id ? { ...entry, status: result.status, last_checked_at: result.last_checked_at, last_response_time_ms: result.response_time_ms, last_status_code: result.http_status_code, last_error: result.error ?? entry.last_error } : entry));
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : 'Connection test failed.');
    } finally {
      setTestingIntegrationId(null);
    }
  };

  const beginExternalScan = (integration: ExternalWebsiteIntegration) => {
    setIntegrationError(null);
    setScanningIntegrationId(integration.id);
    setExternalWorkflow({
      integrationId: integration.id,
      progress: 0,
      running: true,
      approvalPending: false,
      triggerPending: false,
      approvalGranted: false,
      triggerGranted: false,
    });
    setScanResults((current) => {
      const next = { ...current };
      delete next[integration.id];
      return next;
    });
    setIntegrations((current) => current.map((entry) => entry.id === integration.id ? { ...entry, status: 'running' } : entry));
  };

  const approveExternalWorkflow = () => {
    setExternalWorkflow((current) => current ? { ...current, progress: 15, running: true, approvalPending: false, approvalGranted: true } : current);
  };

  const triggerExternalWorkflow = () => {
    setExternalWorkflow((current) => current ? { ...current, progress: 21, running: true, triggerPending: false, triggerGranted: true } : current);
  };

  const handleScanIntegration = (integration: ExternalWebsiteIntegration) => {
    if (scanningIntegrationId === integration.id || externalWorkflow?.integrationId === integration.id) {
      return;
    }
    beginExternalScan(integration);
  };

  const handleDeleteIntegration = async (integration: ExternalWebsiteIntegration) => {
    try {
      await deleteWebsiteIntegration(integration.id);
      setIntegrations((current) => current.filter((entry) => entry.id !== integration.id));
      setConnectionResults((current) => {
        const next = { ...current };
        delete next[integration.id];
        return next;
      });
      setScanResults((current) => {
        const next = { ...current };
        delete next[integration.id];
        return next;
      });
    } catch (err) {
      setIntegrationError(err instanceof Error ? err.message : 'Could not delete the integration.');
    }
  };

  useEffect(() => {
    if (!externalWorkflow) return;
    const integration = integrations.find((entry) => entry.id === externalWorkflow.integrationId);
    if (!integration) return;

    if (externalWorkflow.progress >= EXTERNAL_ANALYSIS_STEPS.length) {
      const finalizeExternalScan = async () => {
        try {
          const result = await scanWebsiteIntegration(integration.id);
          setScanResults((current) => ({ ...current, [integration.id]: result }));
          setIntegrations((current) => current.map((entry) => entry.id === integration.id ? { ...entry, status: result.overall_status, last_checked_at: result.last_checked_at, last_response_time_ms: result.response_time_ms, last_status_code: result.http_status_code, last_error: result.detected_flaws.length > 0 ? result.detected_flaws[0].title : null } : entry));
        } catch (err) {
          setIntegrationError(err instanceof Error ? err.message : 'Scan failed.');
        } finally {
          setScanningIntegrationId(null);
          setExternalWorkflow(null);
        }
      };

      void finalizeExternalScan();
      return;
    }

    if (!externalWorkflow.running) return;

    if (externalWorkflow.progress === 14 && !externalWorkflow.approvalGranted) {
      setExternalWorkflow((current) => current ? { ...current, running: false, approvalPending: true } : current);
      return;
    }

    if (externalWorkflow.progress === 20 && !externalWorkflow.triggerGranted) {
      setExternalWorkflow((current) => current ? { ...current, running: false, triggerPending: true } : current);
      return;
    }

    const timer = window.setTimeout(() => {
      setExternalWorkflow((current) => {
        if (!current) return null;
        const nextProgress = Math.min(EXTERNAL_ANALYSIS_STEPS.length, current.progress + 1);
        return { ...current, progress: nextProgress, running: nextProgress < EXTERNAL_ANALYSIS_STEPS.length };
      });
    }, 1200);

    return () => window.clearTimeout(timer);
  }, [externalWorkflow, integrations]);

  useEffect(() => {
    let cancelled = false;
    const loadMemory = async () => {
      if (demoMode) {
        setMemoryError(null);
        if (demoProgress < 6) {
          setLoadingMemory(false);
          setOrganizationalMemory(null);
          return;
        }
        const fixture = createPaymentApiDemoMemory(demoProgress >= 20 || secondDemoIncident, secondDemoIncident);
        if (demoProgress >= 20 && !secondDemoIncident) {
          setOrganizationalMemory(fixture);
          setLoadingMemory(false);
          return;
        }
        const requestKey = activeScenario.id;
        if (demoMemoryRequests.current.has(requestKey)) return;
        demoMemoryRequests.current.add(requestKey);
        setLoadingMemory(true);
        if (!health?.services?.hindsight_configured) {
          setOrganizationalMemory(fixture);
          setLoadingMemory(false);
          return;
        }
        try {
          const live = await getOrganizationalMemory({
            incidentId: activeScenario.id,
            service: activeScenario.service,
            query: secondDemoIncident
              ? 'Similar payment API connection saturation; prior pool correction outcome and failed database restart'
              : 'Payment API connection pool saturation failed restart successful pool correction deployment',
            signal: AbortSignal.timeout(6500),
          });
          if (!cancelled) {
            if (live.status === 'available' && live.retrieved_memories.length && secondDemoIncident) {
              const lessons = fixture.categories.postmortem_lessons;
              const existingIds = new Set(live.categories.postmortem_lessons.map((record) => record.id));
              const addedLessons = lessons.filter((record) => !existingIds.has(record.id));
              const categories = {
                ...live.categories,
                postmortem_lessons: [...live.categories.postmortem_lessons, ...addedLessons],
              };
              const mergedRecords = [...live.retrieved_memories, ...addedLessons];
              setOrganizationalMemory({
                ...live,
                current_incident: fixture.current_incident,
                categories,
                retrieved_memories: mergedRecords,
                agent_evidence: [...live.agent_evidence, ...addedLessons],
              });
            } else {
              setOrganizationalMemory(live.status === 'available' && live.retrieved_memories.length ? live : fixture);
            }
          }
        } catch {
          if (!cancelled) setOrganizationalMemory(fixture);
        } finally {
          if (!cancelled) setLoadingMemory(false);
        }
        return;
      }
      setLoadingMemory(true);
      setMemoryError(null);
      const query = [
        activeScenario.title,
        activeScenario.currentEvidence.telemetrySummary,
        ...activeScenario.currentEvidence.liveLogs,
      ].join(' ').slice(0, 500);
      try {
        const data = await getOrganizationalMemory({
          incidentId: activeScenario.id,
          service: activeScenario.service,
          query,
        });
        if (!cancelled) setOrganizationalMemory(data);
      } catch (err) {
        if (!cancelled) {
          setMemoryError(err instanceof Error ? err.message : 'Memory lookup failed.');
          setOrganizationalMemory(null);
        }
      } finally {
        if (!cancelled) setLoadingMemory(false);
      }
    };

    void loadMemory();
    return () => { cancelled = true; };
  }, [activeScenario.id, activeScenario.service, health?.services?.hindsight_configured, memoryRetry, demoMode, demoProgress, secondDemoIncident]);

  useEffect(() => {
    if (!demoMode) return;
    setActiveScenario(createPaymentApiDemoScenario(
      !secondDemoIncident && demoProgress >= 17,
      !secondDemoIncident && demoProgress >= 18,
      !secondDemoIncident && demoProgress >= 20,
      !secondDemoIncident && demoProgress >= 19,
      secondDemoIncident,
    ));
    if (demoProgress >= DEMO_STEPS.length) setDemoRunning(false);
  }, [demoMode, demoProgress, secondDemoIncident]);

  useEffect(() => {
    if (!demoMode) return;
    if (secondDemoIncident) {
      setScreen('activeIncident');
    } else if (demoProgress >= 20) {
      setScreen('memory');
    } else if (demoProgress >= 19) {
      setScreen('memory');
    } else if (demoProgress >= 18) {
      setScreen('postmortem');
    } else if (demoProgress >= 15) {
      setScreen('activeIncident');
    } else if (demoProgress >= 11) {
      setScreen('timeMachine');
    } else if (demoProgress >= 10) {
      setScreen('diagnosis');
    } else if (demoProgress >= 6) {
      setScreen('memory');
    } else {
      setScreen('activeIncident');
    }
  }, [demoMode, demoProgress, secondDemoIncident]);

  useEffect(() => {
    if (!demoRunning) return;
    if (demoProgress >= 14 && !demoApproved) {
      setDemoRunning(false);
      return;
    }
    if (demoProgress === 20 && !secondDemoIncident) {
      setDemoRunning(false);
      return;
    }
    if ((demoProgress === 6 || demoProgress === 21) && loadingMemory) return;
    if (demoProgress >= DEMO_STEPS.length) {
      setDemoRunning(false);
      return;
    }
    const timer = window.setTimeout(() => setDemoProgress((progress) => Math.min(DEMO_STEPS.length, progress + 1)), 2200);
    return () => window.clearTimeout(timer);
  }, [demoRunning, demoProgress, demoApproved, secondDemoIncident, loadingMemory]);

  useEffect(() => {
    if (!demoMode || secondDemoIncident || demoProgress < 20 || demoCloudRetention !== 'not-started') return;
    setDemoCloudRetention('pending');
    void retainDemoOutcome()
      .then((result) => setDemoCloudRetention(result.retained ? 'retained' : 'unavailable'))
      .catch(() => setDemoCloudRetention('unavailable'));
  }, [demoMode, demoProgress, demoCloudRetention, secondDemoIncident]);

  const startDemo = () => {
    setDemoMode(true);
    setDemoProgress(0);
    setDemoApproved(false);
    setDemoRejected(false);
    setDemoCloudRetention('not-started');
    setSecondDemoIncident(false);
    demoMemoryRequests.current.clear();
    setOrganizationalMemory(null);
    setScreen('dashboard');
    setActiveScenario(createPaymentApiDemoScenario());
    setDemoRunning(true);
  };

  const approveDemo = () => {
    setDemoApproved(true);
    setDemoRejected(false);
    setDemoProgress(15);
    setDemoRunning(true);
  };

  const rejectDemo = () => {
    setDemoRejected(true);
    setDemoRunning(false);
  };

  const startSecondDemoIncident = () => {
    setSecondDemoIncident(true);
    setDemoProgress(21);
    setDemoRunning(true);
    setScreen('activeIncident');
  };

  const timelineEntries = activeScenario.postmortem.timeline.length
    ? activeScenario.postmortem.timeline
    : [
        { time: 'Now', event: 'Incident under active triage' },
        { time: 'Pending', event: 'Awaiting diagnosis and Hindsight recall' },
      ];

  const renderSeverity = (severity: string) => (
    <span className={`severity-badge ${severityToClass(severity)}`}>{severity}</span>
  );

  return (
    <div className="command-center-shell">
      <a className="skip-link" href="#main-content">Skip to incident workspace</a>
      <header className="topbar">
        <div className="brand-wrap">
          <div className="brand-mark">IC</div>
          <div>
            <div className="eyebrow">Incident Command Center</div>
            <h1>IncidentMind</h1>
          </div>
        </div>

        <div className="header-controls">
          <label className="selector-label">
            <span>Active incident</span>
            <select
              value={activeScenario.id}
              onChange={(event) => {
                const nextScenario = event.target.value === DEMO_INCIDENT_ID
                  ? createPaymentApiDemoScenario()
                  : MOCK_SCENARIOS.find((entry) => entry.id === event.target.value) ?? MOCK_SCENARIOS[0];
                setDemoMode(event.target.value === DEMO_INCIDENT_ID);
                setDemoRunning(false);
                setActiveScenario(nextScenario);
              }}
            >
              {MOCK_SCENARIOS.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.id} • {scenario.service}
                </option>
              ))}
              {demoMode && <option value={DEMO_INCIDENT_ID}>{DEMO_INCIDENT_ID} • payment-api demo</option>}
            </select>
          </label>

          <button className="primary-button demo-launch-button" type="button" onClick={startDemo}>
            <Play size={15} /> {demoMode ? 'Restart Demo' : 'Demo Mode'}
          </button>

          <div className="header-badges">
            <span className={`header-badge ${health?.status === 'healthy' ? 'header-badge--good' : 'header-badge--warn'}`}>
              <i className="status-indicator" />{loadingHealth ? 'Checking API' : health?.status === 'healthy' ? 'API healthy' : healthError ? 'API unavailable' : 'API degraded'}
            </span>
            <span className={`header-badge ${health?.services?.hindsight_configured ? 'header-badge--good' : 'header-badge--muted'}`}>
              <i className="status-indicator" />Hindsight {health?.services?.hindsight_configured ? 'configured' : 'not configured'}
            </span>
            <span className={`header-badge ${health?.services?.groq_configured ? 'header-badge--good' : 'header-badge--warn'}`} title="Groq is optional for the current deterministic diagnosis fallback">
              <i className="status-indicator" />Groq {health?.services?.groq_configured ? 'configured' : 'fallback mode'}
            </span>
            <span className={`header-badge ${health?.services?.postgresql === 'available' ? 'header-badge--good' : health?.services?.postgresql === 'unavailable' ? 'header-badge--warn' : 'header-badge--muted'}`}>
              <i className="status-indicator" />PostgreSQL {health?.services?.postgresql ?? 'checking'}
            </span>
            <button className="icon-button" type="button" onClick={loadHealth} aria-label="Refresh system health" title="Refresh system health" disabled={loadingHealth}>
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
      </header>

      <div className="workspace-shell">
        <aside className="sidebar" aria-label="Incident response workspace">
          {screens.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              className={`nav-button ${screen === key ? 'nav-button--active' : ''}`}
              onClick={() => setScreen(key)}
              aria-current={screen === key ? 'page' : undefined}
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </aside>

        <main className="content-panel" id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <div className="eyebrow">{screenTitles[screen].eyebrow}</div>
              <h2>{screenTitles[screen].title}</h2>
            </div>
            <span className="demo-label">{demoMode ? 'DETERMINISTIC DEMO' : 'SCENARIO DATA'}</span>
          </div>
          {demoMode && (
            <section className="demo-memory-used" aria-label="Memory Used">
              <div className="demo-memory-used__heading">
                <MemoryStick size={16} />
                <strong>Memory Used</strong>
                <span>Provenance stays visible throughout the demo</span>
              </div>
              <div className="demo-memory-used__grid">
                <div><span className="evidence-pill evidence-pill--current-telemetry">Current evidence</span><p>{activeScenario.currentEvidence.telemetrySummary}</p></div>
                <div><span className="evidence-pill evidence-pill--hindsight">Hindsight memory</span><p>{demoProgress >= 6 ? organizationalMemory?.health.status === 'demo-fixture' ? 'Seeded memory fixture INC-419: hard restart failed; pool correction succeeded.' : organizationalMemory?.status === 'available' ? `Live Hindsight recall returned ${organizationalMemory.retrieved_memories.length} records.` : 'Hindsight returned no matching records; the labeled demo memory fixture is shown.' : 'Historical records load at the memory-recall step.'}{demoProgress >= 20 && !secondDemoIncident ? ` First demo outcome: ${demoCloudRetention === 'retained' ? 'retained to Hindsight Cloud.' : demoCloudRetention === 'pending' ? 'Cloud retain pending; local demo lesson is available.' : 'Cloud unavailable; local demo lesson remains available.'}` : ''}{secondDemoIncident ? ' INC-DEMO-002 uses the deterministic retained lesson and avoids the failed restart.' : ''}</p></div>
                <div><span className="evidence-pill evidence-pill--rag">RAG knowledge</span><p>PostgreSQL Connection Pool Troubleshooting: inspect idle sessions, drain/reap safely, then adjust pool capacity.</p></div>
                <div><span className="evidence-pill evidence-pill--ai-inference">AI inference</span><p>Deterministic agent assessment (not a Groq response): likely connection-pool exhaustion after deployment.</p></div>
              </div>
            </section>
          )}
          {demoMode && (
            <section className="demo-run-panel">
              <div className="demo-run-header">
                <div>
                  <span className="memory-kicker">{demoProgress >= DEMO_STEPS.length ? 'DEMO COMPLETE' : demoProgress >= 20 && !secondDemoIncident ? 'FIRST INCIDENT RESOLVED' : demoProgress >= 14 && !demoApproved ? 'HUMAN APPROVAL REQUIRED' : demoRunning ? 'DEMO RUNNING' : demoRejected ? 'DEMO PAUSED' : 'DEMO READY'}</span>
                  <h3>{secondDemoIncident ? 'Payment API recurrence' : 'Payment API incident'} · {demoProgress}/{DEMO_STEPS.length} steps complete</h3>
                  <p>Incident Simulator · deterministic telemetry, seeded Hindsight history, and local runbook context. No Azure or PagerDuty connection required.</p>
                </div>
                <span className={`status-badge ${demoRejected ? 'status-badge--fail' : demoProgress >= 20 ? 'status-badge--success' : demoProgress >= 14 && !demoApproved ? 'status-badge--neutral' : 'status-badge--success'}`}>
                  {demoRejected ? 'Rejected' : demoProgress >= DEMO_STEPS.length ? 'Memory reused' : demoProgress >= 20 ? 'First run resolved' : demoProgress >= 14 && !demoApproved ? 'Awaiting approval' : 'Running'}
                </span>
              </div>
              <progress className="demo-progress" max={DEMO_STEPS.length} value={demoProgress} aria-label={`Incident workflow progress: ${demoProgress} of ${DEMO_STEPS.length} steps`} />
              <span className="sr-only" role="status" aria-live="polite">{demoProgress >= DEMO_STEPS.length ? 'Incident workflow complete.' : demoProgress === 14 && !demoApproved ? 'Waiting for human approval.' : `Workflow step ${demoProgress + 1}: ${DEMO_STEPS[demoProgress]?.title ?? 'in progress'}.`}</span>
              {demoProgress >= 14 && !demoApproved && !demoRejected && (
                <div className="demo-approval-gate">
                  <div><strong>Approve simulated pool correction?</strong><p>Database restart is blocked by INC-419 failed-fix evidence.</p></div>
                  <button className="primary-button" type="button" onClick={approveDemo}>Approve &amp; continue</button>
                  <button className="secondary-button" type="button" onClick={rejectDemo}>Reject</button>
                </div>
              )}
              {demoRejected && <div className="state-banner state-banner--error" role="status">Engineer rejected remediation. No action ran; use Demo Mode to restart the deterministic scenario.</div>}
              {demoProgress >= 20 && !secondDemoIncident && <div className="demo-retain-status" role="status">{demoCloudRetention === 'pending' ? 'Retaining outcome and lessons to Hindsight… Local demo lesson is ready for the second incident.' : demoCloudRetention === 'retained' ? 'Outcome and lessons retained to Hindsight Cloud; local demo lesson is ready for the second incident.' : 'Cloud retention unavailable. The deterministic local lesson remains available; no external retain is claimed.'}</div>}
              {demoProgress === 20 && !secondDemoIncident && <button className="primary-button demo-second-incident-button" type="button" onClick={startSecondDemoIncident}>Trigger similar incident · INC-DEMO-002 <ArrowRight size={15} /></button>}
              {demoProgress >= DEMO_STEPS.length && secondDemoIncident && <div className="demo-retain-status" role="status">INC-DEMO-002 reused the first incident’s lesson and avoided the historically failed database restart. This is a deterministic demo-memory replay.</div>}
              <ol className="demo-step-list">
                {DEMO_STEPS.map((step, index) => {
                  const complete = index < demoProgress;
                  const waiting = index === 14 && demoProgress === 14 && !demoApproved && !demoRejected;
                  const rejected = index === 14 && demoRejected;
                  const current = !complete && index === demoProgress && !waiting && !demoRejected && demoProgress < DEMO_STEPS.length;
                  return (
                    <li className={`demo-step ${complete ? 'demo-step--complete' : waiting || rejected ? 'demo-step--waiting' : current ? 'demo-step--current' : ''}`} key={step.title}>
                      <span className="demo-step__icon">{complete ? <CircleCheck size={16} /> : waiting ? <PauseCircle size={16} /> : <Circle size={16} />}</span>
                      <span className="demo-step__number">{String(index + 1).padStart(2, '0')}</span>
                      <div><strong>{step.title}</strong><p>{step.detail}</p></div>
                      <span className="demo-step__state">{complete ? 'Done' : rejected ? 'Rejected' : waiting ? 'Approval' : current ? 'Running' : 'Pending'}</span>
                    </li>
                  );
                })}
              </ol>
            </section>
          )}
          {loadingHealth && <div className="state-banner state-banner--info" role="status">Checking service health...</div>}
          {healthError && <div className="state-banner state-banner--error" role="alert"><span>{healthError}</span><button type="button" className="text-button" onClick={loadHealth}>Retry</button></div>}

          {screen === 'dashboard' && (
            <div className="screen-stack">
              <section className="summary-header">
                <div>
                  <p>Service health and response posture across the current incident set.</p>
                </div>
                <button type="button" className="primary-button" onClick={() => setScreen('activeIncident')}>
                  Examine active incident
                  <ArrowRight size={16} />
                </button>
              </section>

              <section className="metrics-grid">
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Active incidents</span>
                    <Activity size={16} />
                  </div>
                  <strong>{activeCount}</strong>
                  <p>{MOCK_SCENARIOS.filter((entry) => entry.status !== 'RESOLVED' && entry.severity === 'SEV-1').length} critical · across scenario feed</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Severity</span>
                    <TriangleAlert size={16} />
                  </div>
                  <strong>{activeScenario.severity}</strong>
                  <p>{activeScenario.service} · selected incident</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Affected services</span>
                    <Network size={16} />
                  </div>
                  <strong>{affectedServiceCount}</strong>
                  <p>Distinct affected services</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Response time</span>
                    <Clock3 size={16} />
                  </div>
                  <strong>{activeScenario.postmortem.durationMinutes}m</strong>
                  <p>Recorded incident duration · selected</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>System health</span>
                    <HeartPulse size={16} />
                  </div>
                  {loadingHealth ? <span className="skeleton skeleton-text" role="status" aria-label="Loading system health" /> : <strong>{healthError ? 'Unavailable' : health?.status ?? 'Unknown'}</strong>}
                  <p>{health?.environment ?? 'Environment unavailable'}</p>
                </article>
              </section>

              <section className="dashboard-grid">
                <div className="panel">
                  <div className="section-header">
                    <h3>Active incidents</h3>
                  </div>
                  <div className="incident-list">
                    {MOCK_SCENARIOS.filter((entry) => entry.status !== 'RESOLVED' && entry.status !== 'POSTMORTEM_SAVED').map((entry) => (
                      <button key={entry.id} type="button" className="incident-row" onClick={() => setActiveScenario(entry)}>
                        <div className="incident-row__meta">
                          <span className="incident-id">{entry.id}</span>
                          {renderSeverity(entry.severity)}
                        </div>
                        <div className="incident-row__main">
                          <strong>{entry.service}</strong>
                          <span className="incident-state">{entry.status.replace(/_/g, ' ')}</span>
                        </div>
                        <div className="incident-row__metrics">
                          <span>{entry.summary}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="panel">
                  <div className="section-header">
                    <h3>System health</h3>
                  </div>
                  <div className="health-stack">
                    {[
                      { key: 'api', state: health?.services?.api ?? (loadingHealth ? 'checking' : 'unknown') },
                      { key: 'database', state: health?.services?.database_url_configured ? 'configured' : 'not configured' },
                      { key: 'model', state: health?.services?.model_configured ?? 'unknown' },
                      { key: 'hindsight', state: health?.services?.hindsight_configured ? 'configured' : 'not configured' },
                    ].map(({ key: service, state }) => (
                      <div key={service} className="health-row">
                        <span>{service}</span>
                        <span className={`health-indicator ${state === 'healthy' || state === 'configured' || state === 'available' || state === 'true' ? 'health-indicator--good' : state === 'unavailable' || state === 'not configured' ? 'health-indicator--warn' : 'health-indicator--unknown'}`} aria-hidden="true" />
                        <strong>{String(state).replace(/_/g, ' ')}</strong>
                      </div>
                    ))}
                  </div>
                </div>
              </section>

              <section className="panel">
                <div className="section-header">
                  <h3>Recent incidents</h3>
                </div>
                <div className="recent-table">
                  <div className="recent-row recent-row--head">
                    <span>Incident</span>
                    <span>Service</span>
                    <span>State</span>
                    <span>Response</span>
                  </div>
                  {MOCK_SCENARIOS.map((entry) => (
                    <button key={entry.id} type="button" className="recent-row" onClick={() => { setActiveScenario(entry); setScreen('activeIncident'); }}>
                      <span>{entry.id}</span>
                      <span>{entry.service}</span>
                      <span>{entry.status.replace(/_/g, ' ')}</span>
                      <span>{entry.postmortem.durationMinutes}m duration</span>
                    </button>
                  ))}
                </div>
              </section>
            </div>
          )}

          {screen === 'activeIncident' && (
            <div className="screen-stack">
              <section className="incident-layout">
                <div className="panel left-column">
                  <div className="section-header">
                    <h3>Incident summary</h3>
                    {renderSeverity(activeScenario.severity)}
                  </div>
                  <h2>{activeScenario.title}</h2>
                  <p className="muted-text">{activeScenario.summary}</p>

                  <div className="stack-list">
                    <div className="info-item">
                      <span className="label">Service</span>
                      <strong>{activeScenario.service}</strong>
                    </div>
                    <div className="info-item">
                      <span className="label">Environment</span>
                      <strong>{activeScenario.environment}</strong>
                    </div>
                    <div className="info-item">
                      <span className="label">Status</span>
                      <strong>{activeScenario.status}</strong>
                    </div>
                    <div className="info-item">
                      <span className="label">Response time</span>
                      <strong>{demoMode && activeScenario.status === 'RESOLVED' ? '6m' : demoMode ? 'In progress' : '4m 21s'}</strong>
                    </div>
                    {demoMode && !secondDemoIncident && <div className="info-item"><span className="label">Recent deployment</span><strong>v2.8.4 · 09:24 UTC</strong></div>}
                  </div>

                  <div className="mini-metrics">
                    <div>
                      <span>Error rate</span>
                      <strong>{latestErrorRate}</strong>
                    </div>
                    <div>
                      <span>P99 latency</span>
                      <strong>{latestLatency}</strong>
                    </div>
                    <div>
                      <span>Host CPU</span>
                      <strong>{latestCpu}</strong>
                    </div>
                    {demoMode && <div><span>DB pool</span><strong>{!secondDemoIncident && demoProgress >= 17 ? '52%' : '98%'}</strong></div>}
                  </div>
                </div>

                <div className="panel center-column">
                  <div className="section-header">
                    <h3>Agent execution timeline</h3>
                  </div>
                  <div className="timeline-list">
                    {timelineEntries.map((entry, idx) => (
                      <div key={`${entry.time}-${idx}`} className="timeline-item">
                        <span className="timeline-dot" />
                        <div>
                          <small>{entry.time}</small>
                          <p>{entry.event}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="panel right-column">
                  <div className="section-header"><h3>Diagnosis</h3>{demoMode && sourcePill('AI inference')}</div>
                  <div className="diagnosis-block">
                    <div className="diagnosis-row">
                      <span>Assessment basis</span>
                      <strong>{demoMode ? 'Evidence-linked · deterministic' : `${Math.round(activeScenario.aiInference.confidence * 100)}%`}</strong>
                    </div>
                    <div className="diagnosis-row">
                      <span>Evidence</span>
                      <div className="evidence-stack">
                        {sourcePill('Current telemetry')}
                        {sourcePill('Hindsight')}
                        {sourcePill('RAG')}
                      </div>
                    </div>
                    <p>{activeScenario.aiInference.rootCauseHypothesis}</p>
                    <div className="evidence-list">
                      {activeScenario.aiInference.chainOfThought.map((item) => {
                        return <div className="evidence-row" key={item}>{sourcePill(evidenceSourceFor(item))}<p>{item}</p></div>;
                      })}
                    </div>
                  </div>
                </div>
              </section>
              {demoMode && (
                <section className="demo-evidence-grid">
                  <article className="panel">
                    <div className="section-header"><h3>Investigation metrics</h3><span className="evidence-pill evidence-pill--current-telemetry">Current telemetry</span></div>
                    <p className="demo-evidence-summary">{activeScenario.currentEvidence.telemetrySummary}</p>
                    <div className="demo-metric-trend">
                      <div><span>Error rate trend</span><strong>{activeScenario.currentEvidence.metrics.errorRate.map((metric) => metric.label).join(' → ')}</strong></div>
                      <div><span>P99 latency trend</span><strong>{activeScenario.currentEvidence.metrics.latencyMs.map((metric) => metric.label).join(' → ')}</strong></div>
                    </div>
                  </article>
                  <article className="panel">
                    <div className="section-header"><h3>Payment API logs</h3><span className="status-badge status-badge--neutral">{activeScenario.currentEvidence.liveLogs.length} events</span></div>
                    <ul className="demo-log-list">{activeScenario.currentEvidence.liveLogs.map((log) => <li key={log}><code>{log}</code></li>)}</ul>
                  </article>
                </section>
              )}
            </div>
          )}

          {screen === 'externalIntegrations' && (
            <div className="screen-stack">
              <section className="panel integration-form-panel">
                <div className="section-header">
                  <h3>Connect external service</h3>
                </div>
                <form className="integration-form" onSubmit={handleCreateIntegration}>
                  <div className="integration-form-grid">
                    <label>
                      <span>Website / service name</span>
                      <input required value={integrationForm.name} onChange={(event) => setIntegrationForm((current) => ({ ...current, name: event.target.value }))} placeholder="Enter a website or service name" />
                    </label>
                    <label>
                      <span>Website URL</span>
                      <input required type="url" value={integrationForm.baseUrl} onChange={(event) => setIntegrationForm((current) => ({ ...current, baseUrl: event.target.value }))} placeholder="https://example.com" />
                    </label>
                    <label>
                      <span>Health endpoint</span>
                      <input type="url" value={integrationForm.healthUrl} onChange={(event) => setIntegrationForm((current) => ({ ...current, healthUrl: event.target.value }))} placeholder="https://example.com/health (optional)" />
                    </label>
                    <label>
                      <span>Webhook URL</span>
                      <input type="url" value={integrationForm.webhookUrl} onChange={(event) => setIntegrationForm((current) => ({ ...current, webhookUrl: event.target.value }))} placeholder="https://example.com/webhook" />
                    </label>
                    <label>
                      <span>Service identifier</span>
                      <input value={integrationForm.serviceIdentifier} onChange={(event) => setIntegrationForm((current) => ({ ...current, serviceIdentifier: event.target.value }))} placeholder="Enter service identifier (optional)" />
                    </label>
                    <label>
                      <span>Service name</span>
                      <input value={integrationForm.serviceName} onChange={(event) => setIntegrationForm((current) => ({ ...current, serviceName: event.target.value }))} placeholder="Enter service name (optional)" />
                    </label>
                    <label className="integration-form__full">
                      <span>API key or token</span>
                      <input value={integrationForm.apiKey} onChange={(event) => setIntegrationForm((current) => ({ ...current, apiKey: event.target.value }))} placeholder="Enter API key or token (optional)" type="password" />
                    </label>
                  </div>
                  <div className="integration-form-actions">
                    <button className="primary-button" type="submit" disabled={integrationsLoading}>
                      {editingIntegrationId !== null ? 'Save integration' : 'Connect website'}
                    </button>
                    {editingIntegrationId !== null && (
                      <button className="secondary-button" type="button" onClick={resetIntegrationForm}>Cancel</button>
                    )}
                    {integrationError && <span className="integration-error">{integrationError}</span>}
                  </div>
                </form>
              </section>

              <section className="integration-list-grid">
                {integrations.length === 0 && !integrationsLoading ? (
                  <div className="panel empty-state compact">
                    <p>No external website integrations have been added yet.</p>
                  </div>
                ) : null}

                {integrations.map((integration) => {
                  const connection = connectionResults[integration.id];
                  const result = scanResults[integration.id];
                  const workflow = externalWorkflow?.integrationId === integration.id ? externalWorkflow : null;
                  const workflowVisible = Boolean(workflow || result);
                  const scanProgress = workflow ? workflow.progress : result ? EXTERNAL_ANALYSIS_STEPS.length : 0;
                  const workflowState = workflow?.approvalPending ? 'Approval required' : workflow?.triggerPending ? 'Follow-up required' : workflow ? 'Running' : result ? 'Complete' : 'Queued';
                  return (
                    <article key={integration.id} className="panel integration-card">
                      <div className="section-header">
                        <div>
                          <h3>{integration.name}</h3>
                          <p className="muted-text">{integration.service_name ?? integration.service_identifier ?? 'external service'}</p>
                        </div>
                        <span className={`status-badge ${getStatusBadgeClass(integration.status)}`}>
                          {integration.status}
                        </span>
                      </div>

                      <div className="integration-meta">
                        <div><span>URL</span><strong>{integration.base_url}</strong></div>
                        <div><span>Health</span><strong>{integration.health_url ?? 'Not configured'}</strong></div>
                        <div><span>Last checked</span><strong>{integration.last_checked_at ? new Date(integration.last_checked_at).toLocaleString() : 'Not checked yet'}</strong></div>
                        <div><span>HTTP</span><strong>{integration.last_status_code ? `HTTP ${integration.last_status_code}` : 'Waiting for test'}</strong></div>
                        <div><span>Latency</span><strong>{integration.last_response_time_ms ? `${integration.last_response_time_ms} ms` : 'Unavailable'}</strong></div>
                      </div>

                      <div className="integration-actions">
                        <button className="secondary-button" type="button" onClick={() => void handleTestIntegration(integration)} disabled={testingIntegrationId === integration.id}>
                          {testingIntegrationId === integration.id ? 'Testing...' : 'Test Connection'}
                        </button>
                        <button className="primary-button" type="button" onClick={() => void handleScanIntegration(integration)} disabled={scanningIntegrationId === integration.id || (workflow !== null && workflow.running)}>
                          {scanningIntegrationId === integration.id || (workflow !== null && workflow.running) ? 'Analyzing...' : 'Analyze Website'}
                        </button>
                        <button className="ghost-button" type="button" onClick={() => reuseIntegration(integration)}>Edit</button>
                        <button className="ghost-button" type="button" onClick={() => void handleDeleteIntegration(integration)}>Delete</button>
                      </div>

                      {workflowVisible && (
                        <div className="integration-health-panel">
                          <div className="section-header">
                            <h4>External analysis workflow</h4>
                            <span className={`status-badge ${workflow ? getStatusBadgeClass(workflow.approvalPending || workflow.triggerPending ? 'warning' : workflow.running ? 'running' : 'healthy') : 'status-badge--good'}`}>
                              {workflowState}
                            </span>
                          </div>

                          {workflow && workflow.approvalPending && (
                            <div className="demo-approval-gate">
                              <div>
                                <strong>Approve external findings before finalizing?</strong>
                                <p>The checks have reached the final evidence review stage and need human confirmation before the report is finalized.</p>
                              </div>
                              <button className="primary-button" type="button" onClick={approveExternalWorkflow}>Approve &amp; continue</button>
                            </div>
                          )}

                          {workflow && workflow.triggerPending && (
                            <div className="demo-approval-gate">
                              <div>
                                <strong>Trigger the follow-up audit?</strong>
                                <p>The analysis reached the final handoff stage; a follow-up check can be triggered before the scan is closed.</p>
                              </div>
                              <button className="primary-button" type="button" onClick={triggerExternalWorkflow}>Trigger similar check</button>
                            </div>
                          )}

                          <progress className="demo-progress" max={EXTERNAL_ANALYSIS_STEPS.length} value={scanProgress} aria-label={`External analysis workflow progress for ${integration.name}`} />
                          <ol className="demo-step-list">
                            {EXTERNAL_ANALYSIS_STEPS.map((step, index) => {
                              const complete = (workflow ? index < workflow.progress : !!result) || (result && index < EXTERNAL_ANALYSIS_STEPS.length);
                              const current = workflow ? workflow.running && index === workflow.progress : false;
                              return (
                                <li key={`${integration.id}-${index}`} className={`demo-step ${complete ? 'demo-step--complete' : current ? 'demo-step--current' : ''}`}>
                                  <span className="demo-step__icon">{complete ? <CircleCheck size={16} /> : <Circle size={16} />}</span>
                                  <span className="demo-step__number">{String(index + 1).padStart(2, '0')}</span>
                                  <div><strong>{step}</strong></div>
                                  <span className="demo-step__state">{complete ? 'Done' : current ? 'Running' : 'Pending'}</span>
                                </li>
                              );
                            })}
                          </ol>
                        </div>
                      )}

                      {connection && (
                        <div className="integration-connection-panel">
                          <div className="section-header">
                            <h4>Connection</h4>
                          </div>
                          <div className="integration-row"><span>Status</span><strong>{connection.reachable ? 'CONNECTED' : 'CONNECTION FAILED'}</strong></div>
                          <div className="integration-row"><span>HTTP</span><strong>{connection.http_status_code ? `HTTP ${connection.http_status_code}` : 'Unavailable'}</strong></div>
                          <div className="integration-row"><span>Response time</span><strong>{connection.response_time_ms ? `${connection.response_time_ms} ms` : 'Unavailable'}</strong></div>
                          <div className="integration-row"><span>Reason</span><strong>{connection.error ?? connection.health_status ?? 'Healthy endpoint response'}</strong></div>
                        </div>
                      )}

                      {result && (
                        <div className="integration-health-panel">
                          <div className="section-header">
                            <h4>External System Health</h4>
                          </div>
                          <div className="integration-health-grid">
                            <div><span>Overall</span><strong>{result.overall_status.toUpperCase()}</strong></div>
                            <div><span>API</span><strong>{result.api_status}</strong></div>
                            <div><span>Dependencies</span><strong>{result.dependencies_status}</strong></div>
                            <div><span>Database</span><strong>{result.database_status}</strong></div>
                          </div>
                          <div className="flaw-list">
                            {result.detected_flaws.length === 0 ? (
                              <div className="flaw-card">
                                <div className="flaw-card__header">
                                  <span className="status-badge status-badge--good">No flaws detected</span>
                                </div>
                                <p>No flaws were identified by the checks performed for this website.</p>
                                {result.evidence_summary.length > 0 && (
                                  <ul className="flaw-card__evidence">
                                    {result.evidence_summary.map((entry) => <li key={entry}>{entry}</li>)}
                                  </ul>
                                )}
                              </div>
                            ) : (
                              result.detected_flaws.map((flaw) => (
                                <div key={flaw.flaw_id} className="flaw-card">
                                  <div className="flaw-card__header">
                                    <span className={`severity-badge ${flaw.severity === 'HIGH' ? 'severity--sev2' : flaw.severity === 'MEDIUM' ? 'severity--sev3' : flaw.severity === 'LOW' ? 'severity--sev4' : 'severity--sev4'}`}>{flaw.severity}</span>
                                    <strong>{flaw.title}</strong>
                                    <span className="flaw-card__state">{flaw.status}</span>
                                  </div>
                                  <p>{flaw.description}</p>
                                  <div className="flaw-card__meta">
                                    <span>Affected endpoint: {flaw.affected_endpoint}</span>
                                    <span>Observed: {flaw.observed_value}</span>
                                    <span>Expected: {flaw.expected_value}</span>
                                  </div>
                                  <div className="flaw-card__evidence">
                                    {flaw.evidence.map((entry) => (
                                      <li key={entry}>{entry}</li>
                                    ))}
                                  </div>
                                  <div className="flaw-card__footer">Impact: {flaw.impact}</div>
                                </div>
                              ))
                            )}
                          </div>
                        </div>
                      )}
                    </article>
                  );
                })}
              </section>
            </div>
          )}

          {screen === 'timeline' && (
            <div className="panel">
              <div className="section-header">
                <h3>Incident timeline</h3>
              </div>
              <ol className="full-timeline" aria-label="Incident events in chronological order">
                {timelineEntries.length ? timelineEntries.map((entry, idx) => (
                  <li key={`${entry.time}-${idx}`} className="timeline-row">
                    <span>{entry.time}</span>
                    <div className="timeline-separator" aria-hidden="true" />
                    <p>{entry.event}</p>
                  </li>
                )) : <li className="empty-state compact"><p>No timeline events recorded for this incident.</p></li>}
              </ol>
            </div>
          )}

          {screen === 'hindsightAB' && (
            <div className="screen-stack">
              <section className="panel hindsight-ab-intro">
                <div>
                  <span className="memory-kicker">Controlled evidence comparison</span>
                  <h3>One incident snapshot, evaluated with and without organizational memory.</h3>
                  <p>Both modes receive the exact same payment-api metrics, logs, and deployment context. Mode B adds six memory units retained from the seeded historical record INC-H101 (incident, root cause, two action outcomes, engineer feedback, and postmortem). This view compares evidence and recommendations only; it does not claim faster diagnosis or better operational performance.</p>
                </div>
                <div className="hindsight-ab-incident">
                  <strong>Shared incident input</strong>
                  <span>{HINDSIGHT_AB_COMPARISON.incident.service} · {HINDSIGHT_AB_COMPARISON.incident.context}</span>
                  <ul>{HINDSIGHT_AB_COMPARISON.incident.symptoms.map((symptom) => <li key={symptom}>{symptom}</li>)}</ul>
                </div>
              </section>

              <section className="hindsight-ab-grid" aria-label="Diagnosis mode comparison">
                <article className="panel hindsight-ab-card">
                  <div className="section-header"><div><span className="memory-kicker">Mode A</span><h3>Without memory</h3></div><span className="status-badge status-badge--neutral">0 historical records supplied</span></div>
                  <div className="hindsight-ab-block"><span className="label">Reasoning</span><p>{HINDSIGHT_AB_COMPARISON.withoutMemory.diagnosis}</p></div>
                  <div className="hindsight-ab-block"><span className="label">Recommendations produced · {HINDSIGHT_AB_COMPARISON.withoutMemory.recommendations.length}</span><ul>{HINDSIGHT_AB_COMPARISON.withoutMemory.recommendations.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div className="hindsight-ab-block"><span className="label">Historical failed-fix warnings</span><p>None available in this mode.</p></div>
                  <div className="hindsight-ab-block"><span className="label">Organizational lessons</span><p>None available in this mode.</p></div>
                  <div className="hindsight-ab-block"><span className="label">Evidence references · {HINDSIGHT_AB_COMPARISON.withoutMemory.evidenceRefs.length}</span><p>{HINDSIGHT_AB_COMPARISON.withoutMemory.evidenceRefs.join(' · ')}</p></div>
                </article>

                <article className="panel hindsight-ab-card hindsight-ab-card--memory">
                  <div className="section-header"><div><span className="memory-kicker">Mode B</span><h3>With Hindsight</h3></div><span className="status-badge status-badge--neutral">Seeded comparison · 1 incident</span></div>
                  <div className="hindsight-ab-block"><span className="label">Reasoning</span><p>{HINDSIGHT_AB_COMPARISON.withHindsight.diagnosis}</p></div>
                  <div className="hindsight-ab-block"><span className="label">Historical incident</span><p>{HINDSIGHT_AB_COMPARISON.withHindsight.historicalMatches[0]}</p></div>
                  <div className="hindsight-ab-block"><span className="label">Recommendation produced · {HINDSIGHT_AB_COMPARISON.withHindsight.recommendations.length}</span><ul>{HINDSIGHT_AB_COMPARISON.withHindsight.recommendations.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div className="hindsight-ab-block hindsight-ab-block--warning"><span className="label">Failed-fix warning</span><ul>{HINDSIGHT_AB_COMPARISON.withHindsight.failedFixWarnings.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div className="hindsight-ab-block"><span className="label">Successful fix</span><ul>{HINDSIGHT_AB_COMPARISON.withHindsight.successfulFixes.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div className="hindsight-ab-block"><span className="label">Engineer feedback and postmortem lessons</span><ul>{HINDSIGHT_AB_COMPARISON.withHindsight.lessons.map((item) => <li key={item}>{item}</li>)}</ul></div>
                  <div className="hindsight-ab-block"><span className="label">Evidence references · {HINDSIGHT_AB_COMPARISON.withHindsight.evidenceRefs.length}</span><p>{HINDSIGHT_AB_COMPARISON.withHindsight.evidenceRefs.join(' · ')}</p><small>{HINDSIGHT_AB_COMPARISON.withHindsight.source}</small></div>
                </article>
              </section>
              <section className="panel hindsight-ab-footnote"><strong>Observable difference</strong><p>Mode B can cite an incident, a successful fix, a failed-fix warning, engineer feedback, and postmortem lessons. Mode A sees only the current incident evidence. The recommendation becomes more specific and carries a historical guardrail; no latency, accuracy, or time-saving metric is inferred.</p></section>
            </div>
          )}

          {screen === 'memory' && (
            <div className="screen-stack">
              {memoryError && <div className="state-banner state-banner--error" role="alert"><span>{memoryError}</span><button type="button" className="text-button" onClick={() => setMemoryRetry((value) => value + 1)} disabled={loadingMemory}>Retry</button></div>}
              <section className="memory-overview panel">
                <div>
                  <span className="memory-kicker">Organizational knowledge bank</span>
                  <h3>Hindsight connects today’s incident to accumulated operational experience.</h3>
                  <p>{demoMode ? organizationalMemory?.health.status === 'demo-fixture' ? 'Seeded local Hindsight fixture; remote retrieval was unavailable or not configured.' : 'Live Hindsight recall is shown when available; the second-incident lesson is labeled as a local demo replay.' : 'Records below are returned directly by Hindsight for this incident context. No local seed-data fallback is shown.'}</p>
                </div>
                <div className="memory-bank-status">
                  <span className={`status-badge ${organizationalMemory?.status === 'available' ? 'status-badge--success' : organizationalMemory?.status === 'unavailable' ? 'status-badge--fail' : 'status-badge--neutral'}`}>
                    {loadingMemory ? 'Querying Hindsight' : organizationalMemory?.status ?? 'Unavailable'}
                  </span>
                  <span className="label">Bank</span>
                  <strong>{organizationalMemory?.bank_id ?? 'Not connected'}</strong>
                </div>
              </section>

              <section className="panel retrieval-panel">
                <div className="section-header"><h3>Memory retrieval</h3><span>{sourcePill('Hindsight')}</span></div>
                <ol className="retrieval-flow">
                  <li>
                    <span className="retrieval-flow__index">01</span>
                    <div><strong>Current incident</strong><p>{activeScenario.id} · {activeScenario.service}</p></div>
                    <span className="retrieval-flow__state">Context</span>
                  </li>
                  <li className="retrieval-flow__connector" aria-hidden="true"><ArrowDown size={14} /></li>
                  <li>
                    <span className="retrieval-flow__index">02</span>
                    <div><strong>Hindsight query</strong><p>{organizationalMemory?.current_incident.query ?? [activeScenario.title, activeScenario.currentEvidence.telemetrySummary].join(' ')}</p></div>
                    <span className="retrieval-flow__state">{loadingMemory ? 'Running' : organizationalMemory ? 'Submitted' : 'Waiting'}</span>
                  </li>
                  <li className="retrieval-flow__connector" aria-hidden="true"><ArrowDown size={14} /></li>
                  <li>
                    <span className="retrieval-flow__index">03</span>
                    <div><strong>Retrieved memories</strong><p>{organizationalMemory?.retrieved_memories.length ?? (loadingMemory ? 'Retrieving records' : 'No records available')}</p></div>
                    <span className="retrieval-flow__state">{organizationalMemory?.status ?? (loadingMemory ? 'Running' : 'Unavailable')}</span>
                  </li>
                  <li className="retrieval-flow__connector" aria-hidden="true"><ArrowDown size={14} /></li>
                  <li>
                    <span className="retrieval-flow__index">04</span>
                    <div><strong>Evidence used by agent</strong><p>{organizationalMemory?.agent_evidence.length ?? (loadingMemory ? 'Preparing context' : 'No Hindsight evidence returned')}</p></div>
                    <span className="retrieval-flow__state">{organizationalMemory?.agent_evidence.length ? 'Available' : loadingMemory ? 'Running' : 'Empty'}</span>
                  </li>
                </ol>
              </section>

              <section className="memory-grid organizational-memory-grid">
                {memoryCategoryViews.map(({ key, title }) => {
                  const records = organizationalMemory?.categories[key] ?? [];
                  return (
                    <section className="panel memory-category" key={key}>
                      <div className="section-header"><h3>{title}</h3><span className="memory-count">{records.length}</span></div>
                      {records.length ? records.map((record, index) => (
                        <article className="memory-record" key={`${record.id ?? key}-${index}`}>
                          <div className="memory-record__meta">
                            <span>{record.id ?? 'Source ID unavailable'}</span>
                            <span>{record.type}</span>
                          </div>
                          <p>{record.text || 'Hindsight returned a record without text content.'}</p>
                          {record.tags.length > 0 && <div className="memory-tags">{record.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
                          <details>
                            <summary>Record provenance</summary>
                            <dl>
                              <div><dt>Source</dt><dd>{record.source ?? 'Hindsight'}</dd></div>
                              {typeof record.metadata.incident_id === 'string' && <div><dt>Incident</dt><dd>{record.metadata.incident_id}</dd></div>}
                              {typeof record.metadata.service === 'string' && <div><dt>Service</dt><dd>{record.metadata.service}</dd></div>}
                              {record.score !== null && record.score !== undefined && <div><dt>Recall score</dt><dd>{record.score}</dd></div>}
                              <div><dt>Metadata</dt><dd><code>{JSON.stringify(record.metadata)}</code></dd></div>
                            </dl>
                          </details>
                        </article>
                      )) : (
                        <div className={`empty-state compact ${loadingMemory ? 'memory-loading-state' : ''}`} role={loadingMemory ? 'status' : undefined}>
                          {loadingMemory ? <div className="skeleton-stack" aria-label="Loading Hindsight records"><i /><i /><i /></div> : <p>{organizationalMemory?.status === 'unavailable' ? 'Hindsight is unavailable. No substitute records are shown.' : 'No matching Hindsight records returned for this query.'}</p>}
                        </div>
                      )}
                    </section>
                  );
                })}
              </section>

              <section className="panel agent-evidence-panel">
                <div className="section-header"><div><h3>Evidence surfaced to agents</h3><p className="muted-text">The retrieved records available as Hindsight context, preserving their source identifiers.</p></div></div>
                {organizationalMemory?.agent_evidence.length ? organizationalMemory.agent_evidence.map((record, index) => (
                  <article className="agent-evidence-row" key={`${record.id ?? record.category}-${index}`}>
                    <span className="evidence-pill evidence-pill--hindsight">Hindsight</span>
                    <div><strong>{record.id ?? 'Record ID unavailable'} · {record.category?.replace(/_/g, ' ')}</strong><p>{record.text}</p></div>
                    <span className="agent-evidence-tags">{record.tags.join(', ')}</span>
                  </article>
                )) : <div className="empty-state compact"><p>{loadingMemory ? 'Waiting for retrieved records...' : 'No retrieved Hindsight evidence was returned to the agent context.'}</p></div>}
              </section>

              <LearningCurve />
            </div>
          )}

          {screen === 'diagnosis' && (
            <div className="panel">
              <div className="section-header">
                <h3>Diagnosis</h3>
                <div className="evidence-stack">
                  {sourcePill('Current telemetry')}
                  {sourcePill('Hindsight')}
                  {sourcePill('RAG')}
                </div>
              </div>
              <div className="diagnosis-layout">
                <div className="diagnosis-main">
                  {!demoMode && <div className="confidence-meter">
                    <div className="confidence-meter__fill" style={{ width: `${Math.round(activeScenario.aiInference.confidence * 100)}%` }} />
                  </div>}
                  <div className="diagnosis-summary-row">
                    <span>{demoMode ? 'Reasoning mode' : 'Confidence'}</span>
                    <strong>{demoMode ? 'Deterministic evidence ranking · not Groq' : `${Math.round(activeScenario.aiInference.confidence * 100)}%`}</strong>
                  </div>
                  <p className="diagnosis-body">{activeScenario.aiInference.rootCauseHypothesis}</p>
                </div>

                <div className="evidence-list diagnosis-evidence">
                  {activeScenario.aiInference.chainOfThought.map((item) => {
                    return <article className="evidence-row" key={item}>{sourcePill(evidenceSourceFor(item))}<p>{item}</p></article>;
                  })}
                </div>
              </div>
            </div>
          )}

          {screen === 'blastRadius' && (
            <div className="panel">
              <div className="section-header">
                <h3>Blast radius</h3>
              </div>
              <div className="blast-grid">
                {activeScenario.blastRadius.nodes.map((node) => (
                  <div key={node.id} className={`blast-node blast-node--${node.status.toLowerCase()}`}>
                    <div className="blast-node__top">
                      <strong>{node.name}</strong>
                      <span>{node.type}</span>
                    </div>
                    <div className="blast-node__stats">
                      <span>{node.latency}</span>
                      <span>{node.errorRate}</span>
                    </div>
                    <small>{node.affected ? 'Affected' : 'Healthy'}</small>
                  </div>
                ))}
              </div>
            </div>
          )}

          {screen === 'timeMachine' && (
            <div className="screen-stack">
              <div className="panel">
                <div className="section-header">
                  <h3>Time machine comparison</h3>
                </div>
                <div className="comparison-grid">
                  <div className="compare-card">
                    <span>Current telemetry</span>
                    <strong>Database saturating</strong>
                    <p>Connection pool at {demoMode ? (!secondDemoIncident && demoProgress >= 17 ? '52%' : '98%') : '100%'} utilization with {demoMode ? latestErrorRate : '38%'} user-facing errors and {demoMode ? latestLatency : '4200ms'} p99 latency.</p>
                  </div>
                  <div className="compare-card">
                    <span>Hindsight</span>
                    <strong>INC-419 precedent</strong>
                    <p>INC-419 reports a successful pool resize and idle-connection drain. The incident record reports a 28-minute resolution.</p>
                  </div>
                  <div className="compare-card">
                    <span>RAG</span>
                    <strong>Runbook</strong>
                    <p>postgresql-connection-pool-troubleshooting.md recommends inspecting idle sessions, draining/reaping safely, then adjusting capacity.</p>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="section-header">
                  <h3>Recommended remediation</h3>
                </div>
                <div className="candidate-list">
                  {activeScenario.candidates.map((candidate) => (
                    <article key={candidate.id} className={`candidate-card ${candidate.isRecommended ? 'candidate-card--recommended' : ''}`}>
                      <div className="candidate-card__head">
                        <strong>{candidate.actionName}</strong>
                        <span className={`risk-badge risk-badge--${candidate.safetyLevel.toLowerCase()}`}>
                          {candidate.safetyLevel}
                        </span>
                      </div>
                      <p>{candidate.description}</p>
                      <code>{candidate.commandPreview}</code>
                      <div className="candidate-card__meta">
                        <span>{candidate.historicalPrecedent}</span>
                        <span>{candidate.predictedImpact}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
            </div>
          )}

          {screen === 'remediation' && (
            <div className="panel">
              <div className="section-header">
                <h3>Remediation approval</h3>
              </div>
              <div className="candidate-list">
                {activeScenario.candidates.map((candidate) => (
                  <article key={candidate.id} className={`candidate-card ${candidate.isRecommended ? 'candidate-card--recommended' : ''}`}>
                    <div className="candidate-card__head">
                      <strong>{candidate.actionName}</strong>
                      {candidate.isRecommended ? <span className="status-badge status-badge--success">Recommended</span> : <span className="status-badge status-badge--neutral">Alternate</span>}
                    </div>
                    <p>{candidate.historicalContext}</p>
                    <div className="approval-actions">
                      <button type="button" className="primary-button small-button">Approve</button>
                      <button type="button" className="secondary-button small-button">Modify</button>
                      <button type="button" className="ghost-button small-button">Reject</button>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          )}

          {screen === 'postmortem' && (
            <div className="screen-stack">
              <div className="panel">
                <div className="section-header">
                  <h3>Postmortem</h3>
                  <span className={`status-badge ${activeScenario.postmortem.retainedToHindsight ? 'status-badge--success' : 'status-badge--neutral'}`}>
                    {activeScenario.postmortem.retainedToHindsight ? (demoMode && demoCloudRetention !== 'retained' ? 'Retained in demo memory' : 'Retained to Hindsight') : 'Draft'}
                  </span>
                </div>
                <div className="postmortem-grid">
                  <div>
                    <p className="muted-text">Root cause</p>
                    <strong>{activeScenario.postmortem.rootCause}</strong>
                  </div>
                  <div>
                    <p className="muted-text">Detection source</p>
                    <strong>{activeScenario.postmortem.detectionSource}</strong>
                  </div>
                  <div>
                    <p className="muted-text">Duration</p>
                    <strong>{activeScenario.postmortem.durationMinutes} minutes</strong>
                  </div>
                </div>
                <div className="postmortem-sections">
                  <div><span className="label">Incident summary</span><p>{activeScenario.summary}</p></div>
                  <div><span className="label">Impact</span><p>{activeScenario.blastRadius.estimatedUserImpactPct}% estimated user impact across {activeScenario.blastRadius.affectedServicesCount} services.</p></div>
                  <div><span className="label">Timeline</span><p>{activeScenario.postmortem.timeline.length} events recorded.</p></div>
                  <div><span className="label">Actions attempted</span><p>{activeScenario.candidates.map((candidate) => candidate.actionName).join('; ') || 'No actions recorded.'}</p></div>
                  <div><span className="label">Future prevention</span><ul className="simple-list">{activeScenario.postmortem.correctiveActions.map((action) => <li key={action}>{action}</li>)}</ul></div>
                </div>
                <ul className="simple-list">
                  <li>Engineer rating: {activeScenario.postmortem.engineerRating ?? 'Not provided'}</li>
                </ul>
              </div>

              <div className="panel">
                <div className="section-header">
                  <h3>Lessons captured</h3>
                </div>
                <p className="muted-text">{activeScenario.postmortem.engineerFeedback}</p>
              </div>
            </div>
          )}

          {screen === 'learning' && (
            <div className="screen-stack">
              <div className="panel">
                <div className="section-header">
                  <h3>Learning and memory evolution</h3>
                </div>
                <div className="learning-grid">
                  <div>
                    <span className="label">Hindsight retrieval</span>
                    <strong>{loadingMemory ? 'Loading' : organizationalMemory?.status ?? 'Unavailable'}</strong>
                  </div>
                  <div>
                    <span className="label">Records returned</span>
                    <strong>{organizationalMemory?.retrieved_memories.length ?? (loadingMemory ? 'Loading' : 'Unavailable')}</strong>
                  </div>
                  <div>
                    <span className="label">Memory bank</span>
                    <strong>{organizationalMemory?.bank_id ?? 'Unavailable'}</strong>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="section-header">
                  <h3>Retrieved memory records</h3>
                </div>
                <div className="lineage-list">
                  {organizationalMemory?.retrieved_memories.length ? organizationalMemory.retrieved_memories.map((record, index) => (
                    <div className="lineage-item" key={`${record.id ?? 'memory'}-${index}`}>
                      <span>{record.id ?? 'Hindsight record'} · {record.category?.replace(/_/g, ' ')}</span>
                      <small>{record.text}</small>
                      <small>Tags: {record.tags.length ? record.tags.join(', ') : 'No tags returned'}</small>
                    </div>
                  )) : <div className="empty-state compact"><p>{loadingMemory ? 'Loading Hindsight records...' : 'No Hindsight memory records are available for this incident context.'}</p></div>}
                </div>
              </div>
              <LearningCurve />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
