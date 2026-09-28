import { useEffect, useState, useCallback } from 'react';
import {
  Activity,
  ArrowRight,
  BrainCircuit,
  CircleAlert,
  Clock3,
  Database,
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
import { fetchHealth, getIncidentMemory, HealthCheckResponse, IncidentMemoryResult } from './api/client';
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
  { key: 'memory', label: 'Hindsight Memory', icon: MemoryStick },
  { key: 'diagnosis', label: 'Diagnosis', icon: BrainCircuit },
  { key: 'blastRadius', label: 'Blast Radius', icon: Network },
  { key: 'timeMachine', label: 'Time Machine', icon: TimerReset },
  { key: 'remediation', label: 'Approval', icon: ShieldCheck },
  { key: 'postmortem', label: 'Postmortem', icon: Database },
  { key: 'learning', label: 'Learning', icon: Radar },
];

const sourcePill = (source: 'Current telemetry' | 'Hindsight' | 'RAG') => (
  <span className={`evidence-pill evidence-pill--${source.toLowerCase().replace(/\s+/g, '-')}`}>
    {source}
  </span>
);

const severityToClass = (severity: string) => severity === 'SEV-1' ? 'severity--sev1' : severity === 'SEV-2' ? 'severity--sev2' : severity === 'SEV-3' ? 'severity--sev3' : 'severity--sev4';

export function App() {
  const [activeScenario, setActiveScenario] = useState<IncidentScenario>(MOCK_SCENARIOS[0]);
  const [screen, setScreen] = useState<ScreenKey>('dashboard');
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [incidentMemory, setIncidentMemory] = useState<IncidentMemoryResult | null>(null);
  const [loadingMemory, setLoadingMemory] = useState<boolean>(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);

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
    const loadMemory = async () => {
      setLoadingMemory(true);
      setMemoryError(null);
      try {
        const data = await getIncidentMemory(activeScenario.id);
        setIncidentMemory(data);
      } catch (err) {
        setMemoryError(err instanceof Error ? err.message : 'Memory lookup failed.');
        setIncidentMemory(null);
      } finally {
        setLoadingMemory(false);
      }
    };

    void loadMemory();
  }, [activeScenario.id]);

  const timelineEntries = activeScenario.postmortem.timeline.length
    ? activeScenario.postmortem.timeline
    : [
        { time: 'Now', event: 'Incident under active triage' },
        { time: 'Pending', event: 'Awaiting diagnosis and Hindsight recall' },
      ];

  const relatedIncidents = incidentMemory?.similar_incidents?.length
    ? incidentMemory.similar_incidents
    : activeScenario.historicalEvidence.map((item) => ({
        title: item.title,
        similarity_score: item.similarityScore,
        summary: item.pastRootCause,
      }));

  const successfulFixes = incidentMemory?.successful_fixes?.length
    ? incidentMemory.successful_fixes
    : activeScenario.historicalEvidence.flatMap((entry) =>
        entry.attemptedFixes.filter((fix) => fix.outcome === 'SUCCESS').map((fix) => ({
          action: fix.action,
          outcome: fix.outcome,
          consequence: fix.consequence,
        })),
      );

  const failedFixes = incidentMemory?.failed_fixes?.length
    ? incidentMemory.failed_fixes
    : activeScenario.historicalEvidence.flatMap((entry) =>
        entry.attemptedFixes.filter((fix) => fix.outcome === 'FAILURE').map((fix) => ({
          action: fix.action,
          consequence: fix.consequence,
          engineer_notes: fix.engineerNotes,
        })),
      );

  const engineerLessons = incidentMemory?.engineer_lessons?.length
    ? incidentMemory.engineer_lessons
    : [
        { lesson: activeScenario.postmortem.engineerFeedback ?? 'Continue to validate memory-backed recommendations with engineering review.' },
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
            <span className="header-badge">{health?.services?.api ?? 'api'} online</span>
            <span className="header-badge header-badge--accent">Hindsight connected</span>
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
            >
              <Icon size={16} />
              <span>{label}</span>
            </button>
          ))}
        </aside>

        <main className="content-panel">
          {loadingHealth && (
            <div className="state-banner state-banner--info">Synchronizing system health telemetry...</div>
          )}
          {healthError && (
            <div className="state-banner state-banner--error">{healthError}</div>
          )}

          {screen === 'dashboard' && (
            <div className="screen-stack">
              <section className="summary-header panel">
                <div>
                  <div className="eyebrow">Operations overview</div>
                  <h2>Service health and active incident posture</h2>
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
                  <strong>4</strong>
                  <p>2 Sev-1, 1 Sev-2, 1 Sev-3</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Severity</span>
                    <TriangleAlert size={16} />
                  </div>
                  <strong>SEV-1</strong>
                  <p>Payment gateway saturation</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Affected services</span>
                    <Network size={16} />
                  </div>
                  <strong>12</strong>
                  <p>4 services with customer impact</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>Response time</span>
                    <Clock3 size={16} />
                  </div>
                  <strong>4m 21s</strong>
                  <p>Median MTTA in this environment</p>
                </article>
                <article className="metric-card panel">
                  <div className="metric-card__header">
                    <span>System health</span>
                    <HeartPulse size={16} />
                  </div>
                  <strong>{health?.status ?? 'healthy'}</strong>
                  <p>{health?.environment ?? 'production'} environment</p>
                </article>
              </section>

              <section className="dashboard-grid">
                <div className="panel">
                  <div className="section-header">
                    <h3>Active incidents</h3>
                  </div>
                  <div className="incident-list">
                    {MOCK_SCENARIOS.slice(0, 4).map((entry) => (
                      <button key={entry.id} type="button" className="incident-row" onClick={() => setActiveScenario(entry)}>
                        <div className="incident-row__meta">
                          <span className="incident-id">{entry.id}</span>
                          {renderSeverity(entry.severity)}
                        </div>
                        <div className="incident-row__main">
                          <strong>{entry.service}</strong>
                          <span>{entry.status}</span>
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
                    {['api', 'gateway', 'postgres', 'redis', 'hindsight'].map((service) => (
                      <div key={service} className="health-row">
                        <span>{service}</span>
                        <div className="health-bar"><i style={{ width: service === 'postgres' ? '78%' : service === 'hindsight' ? '92%' : '88%' }} /></div>
                        <strong>{service === 'postgres' ? 'degraded' : 'healthy'}</strong>
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
                    <div key={entry.id} className="recent-row">
                      <span>{entry.id}</span>
                      <span>{entry.service}</span>
                      <span>{entry.status}</span>
                      <span>04m 20s</span>
                    </div>
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
                      <strong>38.2%</strong>
                    </div>
                    <div>
                      <span>P99 latency</span>
                      <strong>4.2s</strong>
                    </div>
                    <div>
                      <span>Queue depth</span>
                      <strong>342</strong>
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
                    <ul>
                      {activeScenario.aiInference.chainOfThought.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
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
                {timelineEntries.map((entry, idx) => (
                  <div key={`${entry.time}-${idx}`} className="timeline-row">
                    <span>{entry.time}</span>
                    <div className="timeline-separator" />
                    <p>{entry.event}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {screen === 'memory' && (
            <div className="screen-stack">
              {loadingMemory && <div className="state-banner state-banner--info">Loading Hindsight memory...</div>}
              {memoryError && <div className="state-banner state-banner--error">{memoryError}</div>}

              {!loadingMemory && !incidentMemory && !memoryError && (
                <div className="empty-state panel">
                  <CircleAlert size={20} />
                  <p>No memory evidence is available for this incident yet.</p>
                </div>
              )}

              {!loadingMemory && incidentMemory && (
                <>
                  <section className="memory-grid">
                    <div className="panel">
                      <div className="section-header">
                        <h3>Similar incidents</h3>
                      </div>
                      <div className="list-stack">
                        {relatedIncidents.length ? relatedIncidents.map((item, idx) => {
                          const record = item as Record<string, any>;
                          const title = typeof record.title === 'string' ? record.title : 'Historical incident';
                          const summary = typeof record.summary === 'string'
                            ? record.summary
                            : typeof record.pastRootCause === 'string'
                              ? record.pastRootCause
                              : 'Memory details unavailable.';

                          return (
                            <article key={`${title}-${idx}`} className="memory-item">
                              <div className="memory-item__head">
                                <strong>{title}</strong>
                                <span>{Math.round((record.similarity_score ?? record.similarityScore ?? 0.82) * 100)}% match</span>
                              </div>
                              <p>{summary}</p>
                            </article>
                          );
                        }) : <div className="empty-state compact"><p>No similar incidents identified.</p></div>}
                      </div>
                    </div>

                    <div className="panel">
                      <div className="section-header">
                        <h3>Successful fixes</h3>
                      </div>
                      <div className="list-stack">
                        {successfulFixes.length ? successfulFixes.map((item, idx) => (
                          <article key={`${item.action}-${idx}`} className="memory-item memory-item--success">
                            <div className="memory-item__head">
                              <strong>{item.action}</strong>
                              <span className="status-badge status-badge--success">Success</span>
                            </div>
                            <p>{item.consequence ?? 'Resolved prior incident without unnecessary blast radius.'}</p>
                          </article>
                        )) : <div className="empty-state compact"><p>No successful fix record.</p></div>}
                      </div>
                    </div>
                  </section>

                  <section className="memory-grid">
                    <div className="panel">
                      <div className="section-header">
                        <h3>Failed fixes</h3>
                      </div>
                      <div className="list-stack">
                        {failedFixes.length ? failedFixes.map((item, idx) => (
                          <article key={`${item.action}-${idx}`} className="memory-item memory-item--fail">
                            <div className="memory-item__head">
                              <strong>{item.action}</strong>
                              <span className="status-badge status-badge--fail">Failed</span>
                            </div>
                            <p>{item.consequence ?? item.engineer_notes ?? 'Failure details unavailable.'}</p>
                          </article>
                        )) : <div className="empty-state compact"><p>No failed action memory.</p></div>}
                      </div>
                    </div>

                    <div className="panel">
                      <div className="section-header">
                        <h3>Engineer lessons</h3>
                      </div>
                      <div className="list-stack">
                        {engineerLessons.length ? engineerLessons.map((item, idx) => (
                          <article key={`${item.lesson}-${idx}`} className="memory-item">
                            <div className="memory-item__head">
                              <strong>Lesson {idx + 1}</strong>
                              <span className="status-badge status-badge--neutral">Operational</span>
                            </div>
                            <p>{item.lesson ?? item.comment ?? 'No lesson captured.'}</p>
                          </article>
                        )) : <div className="empty-state compact"><p>No engineer lessons recorded.</p></div>}
                      </div>
                    </div>
                  </section>
                </>
              )}
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

                <ul className="chain-list">
                  {activeScenario.aiInference.chainOfThought.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
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
                <ul className="simple-list">
                  {activeScenario.postmortem.correctiveActions.map((action) => (
                    <li key={action}>{action}</li>
                  ))}
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
                    <span className="label">Current memory confidence</span>
                    <strong>{incidentMemory?.memory_confidence ? `${Math.round(incidentMemory.memory_confidence * 100)}%` : '84%'}</strong>
                  </div>
                  <div>
                    <span className="label">Retained to Hindsight</span>
                    <strong>{activeScenario.postmortem.retainedToHindsight ? 'Yes' : 'Queued'}</strong>
                  </div>
                  <div>
                    <span className="label">Memory ID</span>
                    <strong>{activeScenario.postmortem.hindsightMemoryId ?? 'MEM-ORG-8821'}</strong>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="section-header">
                  <h3>Evidence lineage</h3>
                </div>
                <div className="lineage-list">
                  <div className="lineage-item">
                    <span>Current telemetry</span>
                    <small>Connection pool reached 100/100 and produced 38% checkout errors.</small>
                  </div>
                  <div className="lineage-item">
                    <span>Hindsight</span>
                    <small>INC-419 historical evidence warned against database restart and validated the pool resize.</small>
                  </div>
                  <div className="lineage-item">
                    <span>RAG</span>
                    <small>Runbook section 4.2 identifies idle transaction drain and pool scaling as the approved path.</small>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
