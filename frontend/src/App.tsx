import { useEffect, useState, useCallback } from 'react';
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
} from 'lucide-react';
import { MOCK_SCENARIOS } from './mock/incidentScenarios';
import { fetchHealth, getOrganizationalMemory, HealthCheckResponse, OrganizationalMemoryCategory, OrganizationalMemoryResult } from './api/client';
import type { IncidentScenario } from './types/incident';
import './App.css';

type ScreenKey =
  | 'dashboard'
  | 'activeIncident'
  | 'timeline'
  | 'memory'
  | 'diagnosis'
  | 'blastRadius'
  | 'timeMachine'
  | 'remediation'
  | 'postmortem'
  | 'learning';

const screens: Array<{ key: ScreenKey; label: string; icon: any }> = [
  { key: 'dashboard', label: 'Dashboard', icon: Layers3 },
  { key: 'activeIncident', label: 'Active Incident', icon: Activity },
  { key: 'timeline', label: 'Incident Timeline', icon: Clock3 },
  { key: 'memory', label: 'Organizational Memory', icon: MemoryStick },
  { key: 'diagnosis', label: 'Diagnosis', icon: BrainCircuit },
  { key: 'blastRadius', label: 'Blast Radius', icon: Network },
  { key: 'timeMachine', label: 'Time Machine', icon: TimerReset },
  { key: 'remediation', label: 'Approval', icon: ShieldCheck },
  { key: 'postmortem', label: 'Postmortem', icon: Database },
  { key: 'learning', label: 'Learning', icon: Radar },
];

type EvidenceSource = 'Current telemetry' | 'Hindsight' | 'RAG';

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
  diagnosis: { title: 'Diagnosis', eyebrow: 'Evidence assessment' },
  blastRadius: { title: 'Blast radius', eyebrow: 'Service impact' },
  timeMachine: { title: 'Incident time machine', eyebrow: 'What-if analysis' },
  remediation: { title: 'Remediation approval', eyebrow: 'Human control' },
  postmortem: { title: 'Postmortem', eyebrow: 'Incident review' },
  learning: { title: 'Learning evolution', eyebrow: 'Memory lifecycle' },
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

  useEffect(() => {
    let cancelled = false;
    const loadMemory = async () => {
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
  }, [activeScenario.id]);

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
                const nextScenario = MOCK_SCENARIOS.find((entry) => entry.id === event.target.value) ?? MOCK_SCENARIOS[0];
                setActiveScenario(nextScenario);
              }}
            >
              {MOCK_SCENARIOS.map((scenario) => (
                <option key={scenario.id} value={scenario.id}>
                  {scenario.id} • {scenario.service}
                </option>
              ))}
            </select>
          </label>

          <div className="header-badges">
            <span className={`header-badge ${health?.status === 'healthy' ? 'header-badge--good' : 'header-badge--warn'}`}>
              <i className="status-indicator" />{loadingHealth ? 'Checking API' : health?.status === 'healthy' ? 'API healthy' : healthError ? 'API unavailable' : 'API degraded'}
            </span>
            <span className={`header-badge ${health?.services?.hindsight_configured ? 'header-badge--good' : 'header-badge--muted'}`}>
              <i className="status-indicator" />Hindsight {health?.services?.hindsight_configured ? 'configured' : 'not configured'}
            </span>
            <button className="icon-button" type="button" onClick={loadHealth} aria-label="Refresh system health" title="Refresh system health" disabled={loadingHealth}>
              <RefreshCw size={15} />
            </button>
          </div>
        </div>
      </header>

      <div className="workspace-shell">
        <aside className="sidebar">
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

        <main className="content-panel">
          <div className="page-heading">
            <div>
              <div className="eyebrow">{screenTitles[screen].eyebrow}</div>
              <h2>{screenTitles[screen].title}</h2>
            </div>
            <span className="demo-label">SCENARIO DATA</span>
          </div>
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
                  <strong>{loadingHealth ? 'Checking' : health?.status ?? 'Unknown'}</strong>
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
                        <div className="health-bar"><i className={state === 'healthy' || state === 'configured' || state === 'available' || state === 'true' ? 'health-bar__fill--good' : 'health-bar__fill--unknown'} /></div>
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
                      <strong>4m 21s</strong>
                    </div>
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
                  <div className="section-header">
                    <h3>Diagnosis</h3>
                  </div>
                  <div className="diagnosis-block">
                    <div className="diagnosis-row">
                      <span>Confidence</span>
                      <strong>{Math.round(activeScenario.aiInference.confidence * 100)}%</strong>
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
            </div>
          )}

          {screen === 'timeline' && (
            <div className="panel">
              <div className="section-header">
                <h3>Incident timeline</h3>
              </div>
              <div className="full-timeline">
                {timelineEntries.length ? timelineEntries.map((entry, idx) => (
                  <div key={`${entry.time}-${idx}`} className="timeline-row">
                    <span>{entry.time}</span>
                    <div className="timeline-separator" />
                    <p>{entry.event}</p>
                  </div>
                )) : <div className="empty-state compact"><p>No timeline events recorded for this incident.</p></div>}
              </div>
            </div>
          )}

          {screen === 'memory' && (
            <div className="screen-stack">
              {memoryError && <div className="state-banner state-banner--error" role="alert">{memoryError}</div>}
              <section className="memory-overview panel">
                <div>
                  <span className="memory-kicker">Organizational knowledge bank</span>
                  <h3>Hindsight connects today’s incident to accumulated operational experience.</h3>
                  <p>Records below are returned directly by Hindsight for this incident context. No local seed-data fallback is shown.</p>
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
                        <div className="empty-state compact">
                          <p>{loadingMemory ? 'Querying Hindsight...' : organizationalMemory?.status === 'unavailable' ? 'Hindsight is unavailable. No substitute records are shown.' : 'No matching Hindsight records returned for this query.'}</p>
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
                  <div className="confidence-meter">
                    <div className="confidence-meter__fill" style={{ width: `${Math.round(activeScenario.aiInference.confidence * 100)}%` }} />
                  </div>
                  <div className="diagnosis-summary-row">
                    <span>Confidence</span>
                    <strong>{Math.round(activeScenario.aiInference.confidence * 100)}%</strong>
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
                    <p>Connection pool exhausted at 100/100 with 38% user-facing error rate.</p>
                  </div>
                  <div className="compare-card">
                    <span>Hindsight</span>
                    <strong>INC-419 precedent</strong>
                    <p>Pool resize and idle connection drain resolved impact in 3 minutes without full DB restart.</p>
                  </div>
                  <div className="compare-card">
                    <span>RAG</span>
                    <strong>Runbook</strong>
                    <p>Section 4.2 corroborates idle transaction cleanup before high-risk service restarts.</p>
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
                  <span className="status-badge status-badge--success">
                    {activeScenario.postmortem.retainedToHindsight ? 'Retained' : 'Draft'}
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
