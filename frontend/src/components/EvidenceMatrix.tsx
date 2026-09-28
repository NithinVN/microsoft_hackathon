import React, { useState } from 'react';
import { CurrentEvidence, HistoricalEvidence, DocumentationEvidence, AIInferenceEvidence } from '../types/incident';
import { Activity, History, BookOpen, Lightbulb, AlertCircle, FileText, CheckCircle2, XCircle } from 'lucide-react';

interface EvidenceMatrixProps {
  currentEvidence: CurrentEvidence;
  historicalEvidence: HistoricalEvidence[];
  documentation: DocumentationEvidence[];
  aiInference: AIInferenceEvidence;
}

export const EvidenceMatrix: React.FC<EvidenceMatrixProps> = ({
  currentEvidence,
  historicalEvidence,
  documentation,
  aiInference,
}) => {
  const [activeTab, setActiveTab] = useState<'all' | 'current' | 'historical' | 'docs' | 'ai'>('all');

  return (
    <div className="card evidence-matrix-card">
      <div className="card-header flex-row">
        <div className="flex-row items-center gap-2">
          <Activity size={18} className="text-blue" />
          <h3 className="card-title">4-Way Evidence Differentiation Matrix</h3>
        </div>
        <div className="evidence-tab-group">
          <button
            className={`evidence-tab ${activeTab === 'all' ? 'active' : ''}`}
            onClick={() => setActiveTab('all')}
          >
            All 4 Sources
          </button>
          <button
            className={`evidence-tab ${activeTab === 'current' ? 'active tab-cyan' : ''}`}
            onClick={() => setActiveTab('current')}
          >
            Current Evidence
          </button>
          <button
            className={`evidence-tab ${activeTab === 'historical' ? 'active tab-purple' : ''}`}
            onClick={() => setActiveTab('historical')}
          >
            Historical Memory (Hindsight)
          </button>
          <button
            className={`evidence-tab ${activeTab === 'docs' ? 'active tab-amber' : ''}`}
            onClick={() => setActiveTab('docs')}
          >
            Documentation (RAG)
          </button>
          <button
            className={`evidence-tab ${activeTab === 'ai' ? 'active tab-green' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            AI Inference
          </button>
        </div>
      </div>

      <div className="card-body">
        <div className="evidence-grid">
          {/* 1. CURRENT EVIDENCE */}
          {(activeTab === 'all' || activeTab === 'current') && (
            <div className="evidence-panel panel-current">
              <div className="panel-header">
                <div className="flex-row items-center gap-2">
                  <Activity size={16} className="text-cyan" />
                  <h4 className="panel-title">1. Current Evidence (Live Telemetry & Logs)</h4>
                </div>
                <span className="source-tag tag-cyan">Observable Telemetry</span>
              </div>
              <div className="panel-content">
                <div className="telemetry-summary-box">
                  <strong>Telemetry Signal:</strong> {currentEvidence.telemetrySummary}
                </div>

                <div className="metric-pills">
                  <div className="metric-pill">
                    <span className="metric-label">P99 Latency:</span>
                    <span className="metric-value text-red">4200ms</span>
                  </div>
                  <div className="metric-pill">
                    <span className="metric-label">Error Rate:</span>
                    <span className="metric-value text-red">38.2%</span>
                  </div>
                  <div className="metric-pill">
                    <span className="metric-label">Pool Used:</span>
                    <span className="metric-value text-red">100/100 (100%)</span>
                  </div>
                </div>

                <div className="log-stream-box">
                  <span className="box-sublabel">Live Captured Log Stream:</span>
                  <div className="terminal-logs">
                    {currentEvidence.liveLogs.map((log, idx) => (
                      <div key={idx} className="log-line">
                        {log}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="traces-box">
                  <span className="box-sublabel">Correlated Distributed Traces:</span>
                  {currentEvidence.traces.map((tr) => (
                    <div key={tr.traceId} className="trace-row">
                      <span className="trace-id">{tr.traceId}</span>
                      <span className="trace-span">{tr.failingSpan}</span>
                      <span className="trace-status text-red">HTTP {tr.httpStatus}</span>
                      <span className="trace-duration">{tr.durationMs}ms</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* 2. HISTORICAL EVIDENCE (HINDSIGHT MEMORY) */}
          {(activeTab === 'all' || activeTab === 'historical') && (
            <div className="evidence-panel panel-historical">
              <div className="panel-header">
                <div className="flex-row items-center gap-2">
                  <History size={16} className="text-purple" />
                  <h4 className="panel-title">2. Historical Evidence (Hindsight Cloud Recall)</h4>
                </div>
                <span className="source-tag tag-purple">Organizational Memory</span>
              </div>
              <div className="panel-content">
                {historicalEvidence.map((hist) => (
                  <div key={hist.hindsightIncidentId} className="hist-incident-card">
                    <div className="hist-incident-top">
                      <span className="hist-id">{hist.hindsightIncidentId}</span>
                      <span className="hist-title">{hist.title}</span>
                      <span className="hist-similarity">
                        {(hist.similarityScore * 100).toFixed(0)}% Match
                      </span>
                    </div>

                    <p className="hist-cause">
                      <strong>Past Root Cause:</strong> {hist.pastRootCause}
                    </p>

                    <div className="hist-fixes-list">
                      <span className="box-sublabel">Past Attempted Actions & Outcomes:</span>
                      {hist.attemptedFixes.map((fix, fidx) => (
                        <div
                          key={fidx}
                          className={`past-fix-item ${fix.outcome === 'FAILURE' ? 'fix-failed' : 'fix-success'}`}
                        >
                          <div className="flex-row items-center">
                            <span className="fix-name">
                              {fix.outcome === 'FAILURE' ? (
                                <XCircle size={14} className="text-red inline-icon" />
                              ) : (
                                <CheckCircle2 size={14} className="text-green inline-icon" />
                              )}
                              {fix.action}
                            </span>
                            <span className={`outcome-badge ${fix.outcome === 'FAILURE' ? 'badge-failed' : 'badge-success'}`}>
                              {fix.outcome}
                            </span>
                          </div>
                          <p className="fix-consequence">{fix.consequence}</p>
                          <div className="fix-notes">
                            <em>Engineer postmortem note: "{fix.engineerNotes}"</em>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="hindsight-reflection-box">
                      <span className="reflection-title">Hindsight Memory Reflection:</span>
                      <p>{hist.hindsightReflection}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. DOCUMENTATION (RAG) */}
          {(activeTab === 'all' || activeTab === 'docs') && (
            <div className="evidence-panel panel-docs">
              <div className="panel-header">
                <div className="flex-row items-center gap-2">
                  <BookOpen size={16} className="text-amber" />
                  <h4 className="panel-title">3. Documentation (RAG Operational Runbooks)</h4>
                </div>
                <span className="source-tag tag-amber">External Knowledge Base</span>
              </div>
              <div className="panel-content">
                {documentation.map((doc, didx) => (
                  <div key={didx} className="doc-card">
                    <div className="doc-top">
                      <FileText size={16} className="text-amber" />
                      <span className="doc-title">{doc.runbookTitle}</span>
                    </div>
                    <div className="doc-section">{doc.matchedSection}</div>
                    <div className="doc-snippet">"{doc.snippet}"</div>
                    <div className="doc-footer">
                      <span className="doc-date">Updated: {doc.lastUpdated}</span>
                      <a href={doc.docUrl} target="_blank" rel="noreferrer" className="doc-link">
                        View Runbook SOP →
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. AI INFERENCE */}
          {(activeTab === 'all' || activeTab === 'ai') && (
            <div className="evidence-panel panel-ai">
              <div className="panel-header">
                <div className="flex-row items-center gap-2">
                  <Lightbulb size={16} className="text-green" />
                  <h4 className="panel-title">4. AI Inference (Groq LLM Synthesis)</h4>
                </div>
                <span className="source-tag tag-green">AI Reasoning Engine</span>
              </div>
              <div className="panel-content">
                <div className="ai-confidence-banner">
                  <div className="confidence-label">DIAGNOSIS CONFIDENCE:</div>
                  <div className="confidence-bar-container">
                    <div
                      className="confidence-bar-fill"
                      style={{ width: `${aiInference.confidence * 100}%` }}
                    ></div>
                  </div>
                  <span className="confidence-pct">{(aiInference.confidence * 100).toFixed(0)}%</span>
                </div>

                <div className="hypothesis-box">
                  <strong>Root Cause Hypothesis:</strong>
                  <p>{aiInference.rootCauseHypothesis}</p>
                </div>

                <div className="chain-of-thought-box">
                  <span className="box-sublabel">Structured Chain of Thought:</span>
                  <ol className="cot-list">
                    {aiInference.chainOfThought.map((thought, tidx) => (
                      <li key={tidx}>{thought}</li>
                    ))}
                  </ol>
                </div>

                <div className="risk-box">
                  <AlertCircle size={16} className="text-amber" />
                  <span><strong>Risk Assessment:</strong> {aiInference.riskAssessment}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
