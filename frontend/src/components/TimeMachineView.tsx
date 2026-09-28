import React from 'react';
import { CandidateRemediation, FailedFixWarning } from '../types/incident';
import { History, AlertTriangle, CheckCircle2, XCircle, Sparkles, ArrowRight, ShieldAlert, Cpu } from 'lucide-react';

interface TimeMachineViewProps {
  candidates: CandidateRemediation[];
  failedFixWarning?: FailedFixWarning;
  onSelectCandidateForApproval: (candidate: CandidateRemediation) => void;
}

export const TimeMachineView: React.FC<TimeMachineViewProps> = ({
  candidates,
  failedFixWarning,
  onSelectCandidateForApproval,
}) => {
  return (
    <div className="time-machine-container">
      {/* 1. Differentiator 2: Failed-Fix Memory Alert Banner */}
      {failedFixWarning && (
        <div className="failed-fix-alert-banner">
          <div className="alert-banner-header">
            <div className="flex-row items-center gap-2">
              <ShieldAlert size={22} className="text-red alert-pulse-icon" />
              <h3 className="alert-banner-title">
                FAILED-FIX MEMORY GUARD: DANGEROUS ACTION DETECTED
              </h3>
            </div>
            <span className="hindsight-provenance-tag">
              <Sparkles size={13} /> Sourced from Hindsight Cloud Memory
            </span>
          </div>

          <div className="alert-banner-body">
            <p className="alert-reason-text">
              <strong>Hindsight Warning: </strong>
              The action <code>{failedFixWarning.dangerousAction}</code> was previously attempted in incident <strong>{failedFixWarning.incidentRef}</strong>.
            </p>
            <div className="alert-historical-consequence">
              <strong>Historical Outcome: </strong> {failedFixWarning.historicalConsequence}
            </div>
            <p className="alert-guard-guidance">
              🛡️ IncidentMind has automatically flagged this action as high risk and blocked default execution to protect production integrity.
            </p>
          </div>
        </div>
      )}

      {/* 2. Differentiator 1: Incident Time Machine Comparison Table */}
      <div className="card mt-4">
        <div className="card-header flex-row">
          <div className="flex-row items-center gap-2">
            <History size={18} className="text-purple" />
            <h3 className="card-title">Incident Time Machine: What-If Historical Precedent Analysis</h3>
          </div>
          <span className="text-xs text-muted">
            Evaluating candidate fixes against institutional memory from previous incidents
          </span>
        </div>

        <div className="card-body">
          <div className="candidates-list">
            {candidates.map((cand) => (
              <div
                key={cand.id}
                className={`candidate-card ${cand.isRecommended ? 'candidate-recommended' : ''} ${
                  cand.historicalPrecedent === 'FAILED_BEFORE' ? 'candidate-failed-precedent' : ''
                }`}
              >
                <div className="candidate-card-header">
                  <div className="flex-row items-center gap-2">
                    <span className="candidate-id-badge">{cand.id}</span>
                    <h4 className="candidate-title">{cand.actionName}</h4>
                    {cand.isRecommended && (
                      <span className="recommended-badge">
                        <Sparkles size={12} /> (Recommended by IncidentMind)
                      </span>
                    )}
                  </div>

                  <div className="candidate-tags">
                    <span className={`precedent-tag tag-${cand.historicalPrecedent.toLowerCase()}`}>
                      {cand.historicalPrecedent === 'SUCCESS_BEFORE' ? (
                        <CheckCircle2 size={13} />
                      ) : cand.historicalPrecedent === 'FAILED_BEFORE' ? (
                        <XCircle size={13} />
                      ) : (
                        <AlertTriangle size={13} />
                      )}
                      {cand.historicalPrecedent.replace('_', ' ')}
                    </span>

                    <span className={`safety-tag tag-${cand.safetyLevel.toLowerCase()}`}>
                      {cand.safetyLevel.replace('_', ' ')}
                    </span>
                  </div>
                </div>

                <p className="candidate-desc">{cand.description}</p>

                <div className="candidate-command-preview">
                  <span className="command-label">
                    <Cpu size={12} className="inline-icon" /> Pre-Approved Vetted Operation:
                  </span>
                  <code>{cand.commandPreview}</code>
                </div>

                <div className="candidate-comparison-grid">
                  <div className="comparison-box hist-box">
                    <span className="comparison-title">HINDSIGHT HISTORICAL PRECEDENT</span>
                    <p>{cand.historicalContext}</p>
                  </div>
                  <div className="comparison-box impact-box">
                    <span className="comparison-title">PREDICTED SYSTEM IMPACT</span>
                    <p>{cand.predictedImpact}</p>
                  </div>
                </div>

                <div className="candidate-actions-footer">
                  {cand.isRecommended ? (
                    <button
                      className="btn-select-approval"
                      onClick={() => onSelectCandidateForApproval(cand)}
                    >
                      <span>Proceed with Recommended Action</span>
                      <ArrowRight size={16} />
                    </button>
                  ) : (
                    <button
                      className="btn-select-override"
                      onClick={() => onSelectCandidateForApproval(cand)}
                    >
                      <span>Review / Manual Override with {cand.id}</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
