import React from 'react';
import { IncidentScenario, ProductLoopStep } from '../types/incident';
import { AlertTriangle, Clock, Server, ArrowRight, ShieldCheck, CheckCircle2 } from 'lucide-react';

interface IncidentHeaderProps {
  scenario: IncidentScenario;
  currentStep: ProductLoopStep;
  onNextStep: () => void;
  onOpenApproval: () => void;
  approvalRequired: boolean;
  isResolved: boolean;
}

export const IncidentHeader: React.FC<IncidentHeaderProps> = ({
  scenario,
  currentStep,
  onNextStep,
  onOpenApproval,
  approvalRequired,
  isResolved,
}) => {
  const getSeverityClass = (sev: string) => {
    switch (sev) {
      case 'SEV-1': return 'badge-sev1';
      case 'SEV-2': return 'badge-sev2';
      case 'SEV-3': return 'badge-sev3';
      default: return 'badge-sev4';
    }
  };

  return (
    <div className="incident-header-banner">
      <div className="banner-top-row">
        <div className="flex-row items-center gap-3">
          <span className={`severity-badge ${getSeverityClass(scenario.severity)}`}>
            {scenario.severity}
          </span>
          <span className="incident-id-tag">{scenario.id}</span>
          <h2 className="incident-banner-title">{scenario.title}</h2>
        </div>

        <div className="banner-controls">
          {approvalRequired && (
            <button className="btn-pulse-approval" onClick={onOpenApproval}>
              <ShieldCheck size={18} />
              <span>Human Approval Required</span>
            </button>
          )}

          {!isResolved && !approvalRequired && (
            <button className="btn-next-step" onClick={onNextStep}>
              <span>Advance Step</span>
              <ArrowRight size={16} />
            </button>
          )}

          {isResolved && (
            <div className="resolved-tag">
              <CheckCircle2 size={18} className="text-green" />
              <span>Incident Remediated & Verified</span>
            </div>
          )}
        </div>
      </div>

      <div className="banner-meta-row">
        <div className="meta-item">
          <Server size={14} className="text-muted" />
          <span>Root Service: <strong>{scenario.service}</strong></span>
        </div>
        <div className="meta-item">
          <Clock size={14} className="text-muted" />
          <span>Started: <strong>{new Date(scenario.startedAt).toLocaleTimeString()}</strong></span>
        </div>
        <div className="meta-item">
          <AlertTriangle size={14} className="text-muted" />
          <span>Environment: <strong>{scenario.environment}</strong></span>
        </div>
        <div className="meta-item">
          <span>Loop Phase: <strong className="text-purple uppercase">{currentStep.replace('_', ' ')}</strong></span>
        </div>
      </div>

      <p className="incident-summary-text">{scenario.summary}</p>
    </div>
  );
};
