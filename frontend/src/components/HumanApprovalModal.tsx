import React, { useState } from 'react';
import { CandidateRemediation } from '../types/incident';
import { ShieldCheck, AlertTriangle, CheckCircle2, X, Terminal, ShieldAlert, Cpu } from 'lucide-react';

interface HumanApprovalModalProps {
  candidate: CandidateRemediation;
  isOpen: boolean;
  onClose: () => void;
  onApprove: (engineerNotes: string) => void;
  onReject: () => void;
}

export const HumanApprovalModal: React.FC<HumanApprovalModalProps> = ({
  candidate,
  isOpen,
  onClose,
  onApprove,
  onReject,
}) => {
  const [engineerNotes, setEngineerNotes] = useState<string>('Approved based on Hindsight INC-419 historical precedent.');
  const [confirmedSafety, setConfirmedSafety] = useState<boolean>(true);

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop">
      <div className="modal-card">
        <div className="modal-header">
          <div className="flex-row items-center gap-2">
            <ShieldCheck size={24} className="text-green" />
            <h3 className="modal-title">Human-in-the-Loop Remediation Approval Gate</h3>
          </div>
          <button className="modal-close-btn" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          <div className="approval-guard-notice">
            <ShieldAlert size={18} className="text-amber" />
            <div>
              <strong>Strict Guardrail Enforcement:</strong>
              <p>
                Architectural Rules #8, #9 & #10: Autonomous arbitrary shell or raw SQL execution is forbidden. All remediation commands are strictly mapped to vetted, parameterized runbook routines.
              </p>
            </div>
          </div>

          <div className="selected-action-detail">
            <div className="detail-row">
              <span className="detail-label">ACTION ID:</span>
              <span className="detail-value font-mono">{candidate.id}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">TARGET ACTION:</span>
              <span className="detail-value font-bold">{candidate.actionName}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">SAFETY CLASSIFICATION:</span>
              <span className={`safety-tag tag-${candidate.safetyLevel.toLowerCase()}`}>
                {candidate.safetyLevel}
              </span>
            </div>
          </div>

          <div className="modal-command-box">
            <div className="command-box-top">
              <Terminal size={14} className="text-muted" />
              <span>Vetted Routine Call:</span>
            </div>
            <pre className="command-pre">
              <code>{candidate.commandPreview}</code>
            </pre>
          </div>

          <div className="historical-validation-box">
            <div className="flex-row items-center gap-2 mb-1">
              <Cpu size={15} className="text-purple" />
              <strong className="text-xs uppercase text-purple">Hindsight Memory Validation:</strong>
            </div>
            <p className="text-sm text-secondary">{candidate.historicalContext}</p>
          </div>

          <div className="form-group mt-3">
            <label className="form-label">On-Call Engineer Audit Rationale / Notes:</label>
            <textarea
              className="form-textarea"
              rows={2}
              value={engineerNotes}
              onChange={(e) => setEngineerNotes(e.target.value)}
              placeholder="Provide reason for approval or execution context..."
            />
          </div>

          <label className="checkbox-label mt-2">
            <input
              type="checkbox"
              checked={confirmedSafety}
              onChange={(e) => setConfirmedSafety(e.target.checked)}
            />
            <span>I have verified the blast radius and confirm execution of this pre-approved action.</span>
          </label>
        </div>

        <div className="modal-footer">
          <button className="btn-secondary" onClick={onReject}>
            <AlertTriangle size={15} className="text-red" />
            <span>Reject Action</span>
          </button>

          <button
            className="btn-approve"
            disabled={!confirmedSafety}
            onClick={() => onApprove(engineerNotes)}
          >
            <CheckCircle2 size={16} />
            <span>Approve & Execute Remediation</span>
          </button>
        </div>
      </div>
    </div>
  );
};
