import React from 'react';
import { ProductLoopStep } from '../types/incident';
import { Check, ShieldCheck, Sparkles } from 'lucide-react';

interface ProductLoopStepperProps {
  currentStep: ProductLoopStep;
  completedSteps: ProductLoopStep[];
  onSelectStep: (step: ProductLoopStep) => void;
}

const STEPS: { id: ProductLoopStep; label: string; isHighlight?: boolean; isGate?: boolean }[] = [
  { id: 'incident', label: '1. Incident' },
  { id: 'investigation', label: '2. Investigation' },
  { id: 'blast_radius', label: '3. Blast Radius' },
  { id: 'memory_recall', label: '4. Memory Recall', isHighlight: true },
  { id: 'diagnosis', label: '5. Diagnosis' },
  { id: 'what_if', label: '6. What-If Analysis', isHighlight: true },
  { id: 'approval', label: '7. Human Approval', isGate: true },
  { id: 'remediation', label: '8. Remediation' },
  { id: 'verification', label: '9. Verification' },
  { id: 'postmortem', label: '10. Postmortem' },
  { id: 'memory_retain', label: '11. Hindsight Retain', isHighlight: true },
];

export const ProductLoopStepper: React.FC<ProductLoopStepperProps> = ({
  currentStep,
  completedSteps,
  onSelectStep,
}) => {
  return (
    <div className="stepper-container">
      <div className="stepper-title-row">
        <span className="stepper-title">CORE PRODUCT LOOP</span>
        <span className="text-muted text-xs">
          Autonomous Investigation → Hindsight Memory Matching → Human Approval → Verified Learning
        </span>
      </div>

      <div className="stepper-track">
        {STEPS.map((step) => {
          const isCurrent = currentStep === step.id;
          const isDone = completedSteps.includes(step.id);

          let stepClass = 'stepper-node';
          if (isCurrent) stepClass += ' active';
          if (isDone) stepClass += ' completed';
          if (step.isHighlight) stepClass += ' highlight-node';
          if (step.isGate) stepClass += ' gate-node';

          return (
            <button
              key={step.id}
              className={stepClass}
              onClick={() => onSelectStep(step.id)}
              title={`Jump to view: ${step.label}`}
            >
              <div className="node-indicator">
                {isDone ? (
                  <Check size={12} strokeWidth={3} />
                ) : step.isGate ? (
                  <ShieldCheck size={12} strokeWidth={2.5} />
                ) : step.isHighlight ? (
                  <Sparkles size={12} />
                ) : (
                  <span className="node-dot"></span>
                )}
              </div>
              <span className="node-label">{step.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
