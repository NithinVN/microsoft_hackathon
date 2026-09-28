import React from 'react';
import { ProductLoopStep } from '../types/incident';
import { Bot, Search, Network, Brain, Stethoscope, Wrench, CheckCircle, Clock } from 'lucide-react';

interface AgentPipelineProps {
  currentStep: ProductLoopStep;
  completedSteps: ProductLoopStep[];
}

interface AgentCard {
  id: string;
  name: string;
  role: string;
  description: string;
  icon: React.ReactNode;
  activeSteps: ProductLoopStep[];
  completedSteps: ProductLoopStep[];
  outputSummary: string;
}

export const AgentPipeline: React.FC<AgentPipelineProps> = ({
  currentStep,
  completedSteps,
}) => {
  const agents: AgentCard[] = [
    {
      id: 'orchestrator',
      name: 'Incident Orchestrator',
      role: 'State Machine Coordinator',
      description: 'Manages LangGraph execution states, coordinates agent handoffs, and ensures human approval gates.',
      icon: <Bot size={18} className="text-blue" />,
      activeSteps: ['incident'],
      completedSteps: ['investigation', 'blast_radius', 'memory_recall', 'diagnosis', 'what_if', 'approval', 'remediation', 'verification', 'postmortem', 'memory_retain'],
      outputSummary: 'Active incident initialized. Dispatched parallel investigation and telemetry observers.',
    },
    {
      id: 'investigation',
      name: 'Investigation Agent',
      role: 'Evidence Collector',
      description: 'Collects live telemetry, analyzes logs, correlates span traces, and extracts system error signatures.',
      icon: <Search size={18} className="text-cyan" />,
      activeSteps: ['investigation'],
      completedSteps: ['blast_radius', 'memory_recall', 'diagnosis', 'what_if', 'approval', 'remediation', 'verification', 'postmortem', 'memory_retain'],
      outputSummary: 'Identified 100/100 pool saturation in payment-processor; extracted 2 failing trace spans.',
    },
    {
      id: 'blast_radius',
      name: 'Blast Radius Agent',
      role: 'Topology Impact Evaluator',
      description: 'Traverses service topology graph to isolate impacted upstream callers and tier-1 user exposure.',
      icon: <Network size={18} className="text-amber" />,
      activeSteps: ['blast_radius'],
      completedSteps: ['memory_recall', 'diagnosis', 'what_if', 'approval', 'remediation', 'verification', 'postmortem', 'memory_retain'],
      outputSummary: 'Impact isolated to 4 services; estimated 38% user payment checkout degradation.',
    },
    {
      id: 'memory',
      name: 'Memory Agent (Hindsight Cloud)',
      role: 'Organizational Memory Retrieval',
      description: 'Executes semantic recall across previous company incidents, failed remediation attempts, and postmortems.',
      icon: <Brain size={18} className="text-purple" />,
      activeSteps: ['memory_recall'],
      completedSteps: ['diagnosis', 'what_if', 'approval', 'remediation', 'verification', 'postmortem', 'memory_retain'],
      outputSummary: 'Recalled INC-419 (similarity 0.94); discovered failed DB reboot causing 45m thundering herd downtime.',
    },
    {
      id: 'diagnosis',
      name: 'Diagnosis Agent',
      role: 'Root Cause Synthesizer',
      description: 'Synthesizes current telemetry evidence with historical Hindsight experience and operational runbooks.',
      icon: <Stethoscope size={18} className="text-green" />,
      activeSteps: ['diagnosis'],
      completedSteps: ['what_if', 'approval', 'remediation', 'verification', 'postmortem', 'memory_retain'],
      outputSummary: 'Formulated 96% confidence hypothesis: unreleased idle connections + promotional surge.',
    },
    {
      id: 'remediation',
      name: 'Remediation Agent',
      role: 'Guarded Action Planner',
      description: 'Evaluates candidate fixes against past failures (What-If), issues Failed-Fix warnings, and waits for Human Approval.',
      icon: <Wrench size={18} className="text-red" />,
      activeSteps: ['what_if', 'approval', 'remediation', 'verification'],
      completedSteps: ['postmortem', 'memory_retain'],
      outputSummary: 'Formulated FIX-A (Pool resize + clean idle); blocked dangerous reboot FIX-B via Failed-Fix memory.',
    },
  ];

  return (
    <div className="card agent-pipeline-card">
      <div className="card-header flex-row">
        <div className="flex-row items-center gap-2">
          <Bot size={18} className="text-blue" />
          <h3 className="card-title">Primary Agent State Machine</h3>
        </div>
        <span className="text-xs text-muted">6 Autonomous Agents with Hindsight Memory Layer</span>
      </div>

      <div className="card-body">
        <div className="agent-grid">
          {agents.map((agent) => {
            const isCurrentlyActive = agent.activeSteps.includes(currentStep);
            const isAgentCompleted = agent.completedSteps.some((step) => completedSteps.includes(step));

            let statusBadge = (
              <span className="agent-status-pill idle">
                <Clock size={12} /> Idle
              </span>
            );

            if (isCurrentlyActive) {
              statusBadge = (
                <span className="agent-status-pill active-pill">
                  <span className="pulse-dot"></span> Running
                </span>
              );
            } else if (isAgentCompleted) {
              statusBadge = (
                <span className="agent-status-pill completed-pill">
                  <CheckCircle size={12} /> Completed
                </span>
              );
            }

            return (
              <div
                key={agent.id}
                className={`agent-box ${isCurrentlyActive ? 'agent-box-active' : ''}`}
              >
                <div className="agent-box-top">
                  <div className="agent-avatar">{agent.icon}</div>
                  <div className="agent-box-meta">
                    <span className="agent-name">{agent.name}</span>
                    <span className="agent-role">{agent.role}</span>
                  </div>
                  {statusBadge}
                </div>

                <p className="agent-desc">{agent.description}</p>

                {(isCurrentlyActive || isAgentCompleted) && (
                  <div className="agent-output-box">
                    <span className="output-label">OUTPUT OBSERVATION:</span>
                    <p className="output-text">{agent.outputSummary}</p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
