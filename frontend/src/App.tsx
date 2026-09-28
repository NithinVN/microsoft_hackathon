import { useState, useEffect, useCallback } from 'react';
import { MOCK_SCENARIOS } from './mock/incidentScenarios';
import { IncidentScenario, ProductLoopStep, CandidateRemediation } from './types/incident';
import { Navbar } from './components/Navbar';
import { IncidentHeader } from './components/IncidentHeader';
import { ProductLoopStepper } from './components/ProductLoopStepper';
import { AgentPipeline } from './components/AgentPipeline';
import { EvidenceMatrix } from './components/EvidenceMatrix';
import { BlastRadiusViewer } from './components/BlastRadiusViewer';
import { TimeMachineView } from './components/TimeMachineView';
import { HumanApprovalModal } from './components/HumanApprovalModal';
import { PostmortemLearningLoop } from './components/PostmortemLearningLoop';
import { HealthStatus } from './components/HealthStatus';
import { fetchHealth, HealthCheckResponse } from './api/client';
import { Layers, Activity, History, Network, Brain, Server } from 'lucide-react';
import './App.css';

const STEP_SEQUENCE: ProductLoopStep[] = [
  'incident',
  'investigation',
  'blast_radius',
  'memory_recall',
  'diagnosis',
  'what_if',
  'approval',
  'remediation',
  'verification',
  'postmortem',
  'memory_retain',
];

export function App() {
  const [scenarios] = useState<IncidentScenario[]>(MOCK_SCENARIOS);
  const [activeScenario, setActiveScenario] = useState<IncidentScenario>(MOCK_SCENARIOS[0]);
  const [currentStep, setCurrentStep] = useState<ProductLoopStep>('incident');
  const [completedSteps, setCompletedSteps] = useState<ProductLoopStep[]>(['incident']);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<'overview' | 'evidence' | 'timemachine' | 'blastradius' | 'learning' | 'system'>('overview');
  
  // Approval Modal State
  const [isApprovalOpen, setIsApprovalOpen] = useState<boolean>(false);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateRemediation>(
    activeScenario.candidates.find((c) => c.isRecommended) || activeScenario.candidates[0]
  );
  
  // Postmortem Retain State
  const [isRetaining, setIsRetaining] = useState<boolean>(false);

  // Health Status
  const [health, setHealth] = useState<HealthCheckResponse | null>(null);
  const [loadingHealth, setLoadingHealth] = useState<boolean>(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  const loadHealth = useCallback(async () => {
    setLoadingHealth(true);
    setHealthError(null);
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch (err: unknown) {
      setHealthError(err instanceof Error ? err.message : 'Failed to connect to backend API');
    } finally {
      setLoadingHealth(false);
    }
  }, []);

  useEffect(() => {
    loadHealth();
  }, [loadHealth]);

  // Handle switching scenario
  const handleSelectScenario = (scenario: IncidentScenario) => {
    setActiveScenario(scenario);
    setCurrentStep('incident');
    setCompletedSteps(['incident']);
    setIsPlaying(false);
    setIsApprovalOpen(false);
    setSelectedCandidate(scenario.candidates.find((c) => c.isRecommended) || scenario.candidates[0]);
  };

  // Reset current scenario
  const handleReset = () => {
    setCurrentStep('incident');
    setCompletedSteps(['incident']);
    setIsPlaying(false);
    setIsApprovalOpen(false);
  };

  // Advance one step forward in the product loop
  const handleNextStep = useCallback(() => {
    const currentIndex = STEP_SEQUENCE.indexOf(currentStep);
    if (currentIndex < STEP_SEQUENCE.length - 1) {
      const nextStep = STEP_SEQUENCE[currentIndex + 1];
      
      // If advancing to approval step, trigger approval modal
      if (nextStep === 'approval') {
        setIsApprovalOpen(true);
      }

      setCurrentStep(nextStep);
      setCompletedSteps((prev) => (prev.includes(nextStep) ? prev : [...prev, nextStep]));
    } else {
      setIsPlaying(false);
    }
  }, [currentStep]);

  // Auto-run loop timer
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    if (isPlaying) {
      if (currentStep === 'what_if') {
        // Pause at approval gate
        setIsPlaying(false);
        setIsApprovalOpen(true);
      } else if (currentStep === 'memory_retain') {
        setIsPlaying(false);
      } else {
        timer = setTimeout(() => {
          handleNextStep();
        }, 2200);
      }
    }
    return () => clearTimeout(timer);
  }, [isPlaying, currentStep, handleNextStep]);

  // Toggle Auto-play
  const handleToggleAutoPlay = () => {
    if (currentStep === 'memory_retain') {
      handleReset();
    }
    setIsPlaying((prev) => !prev);
  };

  // Human Approval Action
  const handleApprove = (_notes: string) => {
    setIsApprovalOpen(false);
    // Mark approval completed and move to remediation
    setCompletedSteps((prev) => [...prev, 'approval', 'remediation', 'verification']);
    setCurrentStep('verification');
    setTimeout(() => {
      setCurrentStep('postmortem');
      setCompletedSteps((prev) => [...prev, 'postmortem']);
    }, 1500);
  };

  const handleReject = () => {
    setIsApprovalOpen(false);
    alert('Remediation action rejected by on-call engineer. Incident remains in WHAT_IF analysis phase.');
  };

  // Retain to Hindsight Cloud
  const handleRetainToHindsight = (_feedback: string, rating: number) => {
    setIsRetaining(true);
    setTimeout(() => {
      setIsRetaining(false);
      setActiveScenario((prev) => ({
        ...prev,
        postmortem: {
          ...prev.postmortem,
          retainedToHindsight: true,
          engineerRating: rating,
          hindsightMemoryId: `MEM-HINDSIGHT-${Math.floor(1000 + Math.random() * 9000)}`,
        },
      }));
      setCompletedSteps((prev) => [...prev, 'memory_retain']);
      setCurrentStep('memory_retain');
    }, 1200);
  };

  const isResolved = completedSteps.includes('verification');

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <Navbar
        scenarios={scenarios}
        activeScenario={activeScenario}
        onSelectScenario={handleSelectScenario}
        onReset={handleReset}
        onAutoPlay={handleToggleAutoPlay}
        isPlaying={isPlaying}
      />

      {/* Main Container */}
      <main className="main-content">
        {/* Incident Header Banner */}
        <IncidentHeader
          scenario={activeScenario}
          currentStep={currentStep}
          onNextStep={handleNextStep}
          onOpenApproval={() => setIsApprovalOpen(true)}
          approvalRequired={currentStep === 'approval' || currentStep === 'what_if'}
          isResolved={isResolved}
        />

        {/* 10-Step Core Product Loop Stepper */}
        <ProductLoopStepper
          currentStep={currentStep}
          completedSteps={completedSteps}
          onSelectStep={(step) => setCurrentStep(step)}
        />

        {/* Navigation Tabs for Views */}
        <div className="view-tabs-bar mt-4">
          <button
            className={`view-tab ${activeView === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveView('overview')}
          >
            <Layers size={16} />
            <span>Full Pipeline & Agents</span>
          </button>

          <button
            className={`view-tab ${activeView === 'evidence' ? 'active' : ''}`}
            onClick={() => setActiveView('evidence')}
          >
            <Activity size={16} />
            <span>4-Way Evidence Matrix</span>
          </button>

          <button
            className={`view-tab ${activeView === 'timemachine' ? 'active' : ''}`}
            onClick={() => setActiveView('timemachine')}
          >
            <History size={16} />
            <span>Incident Time Machine & Failed-Fix</span>
          </button>

          <button
            className={`view-tab ${activeView === 'blastradius' ? 'active' : ''}`}
            onClick={() => setActiveView('blastradius')}
          >
            <Network size={16} />
            <span>Blast Radius Mesh</span>
          </button>

          <button
            className={`view-tab ${activeView === 'learning' ? 'active' : ''}`}
            onClick={() => setActiveView('learning')}
          >
            <Brain size={16} />
            <span>Postmortem & Learning Loop</span>
          </button>

          <button
            className={`view-tab ${activeView === 'system' ? 'active' : ''}`}
            onClick={() => setActiveView('system')}
          >
            <Server size={16} />
            <span>System Health & Config</span>
          </button>
        </div>

        {/* Dynamic View Content */}
        <div className="mt-4">
          {activeView === 'overview' && (
            <div className="overview-stack">
              <AgentPipeline
                currentStep={currentStep}
                completedSteps={completedSteps}
              />

              <div className="mt-6">
                <TimeMachineView
                  candidates={activeScenario.candidates}
                  failedFixWarning={activeScenario.failedFixWarning}
                  onSelectCandidateForApproval={(cand) => {
                    setSelectedCandidate(cand);
                    setIsApprovalOpen(true);
                  }}
                />
              </div>

              <div className="mt-6">
                <EvidenceMatrix
                  currentEvidence={activeScenario.currentEvidence}
                  historicalEvidence={activeScenario.historicalEvidence}
                  documentation={activeScenario.documentation}
                  aiInference={activeScenario.aiInference}
                />
              </div>

              {isResolved && (
                <div className="mt-6">
                  <PostmortemLearningLoop
                    postmortem={activeScenario.postmortem}
                    onRetainToHindsight={handleRetainToHindsight}
                    isRetaining={isRetaining}
                  />
                </div>
              )}
            </div>
          )}

          {activeView === 'evidence' && (
            <EvidenceMatrix
              currentEvidence={activeScenario.currentEvidence}
              historicalEvidence={activeScenario.historicalEvidence}
              documentation={activeScenario.documentation}
              aiInference={activeScenario.aiInference}
            />
          )}

          {activeView === 'timemachine' && (
            <TimeMachineView
              candidates={activeScenario.candidates}
              failedFixWarning={activeScenario.failedFixWarning}
              onSelectCandidateForApproval={(cand) => {
                setSelectedCandidate(cand);
                setIsApprovalOpen(true);
              }}
            />
          )}

          {activeView === 'blastradius' && (
            <BlastRadiusViewer blastRadius={activeScenario.blastRadius} />
          )}

          {activeView === 'learning' && (
            <PostmortemLearningLoop
              postmortem={activeScenario.postmortem}
              onRetainToHindsight={handleRetainToHindsight}
              isRetaining={isRetaining}
            />
          )}

          {activeView === 'system' && (
            <HealthStatus
              health={health}
              loading={loadingHealth}
              error={healthError}
              onRefresh={loadHealth}
            />
          )}
        </div>
      </main>

      {/* Human-in-the-Loop Approval Modal */}
      <HumanApprovalModal
        candidate={selectedCandidate}
        isOpen={isApprovalOpen}
        onClose={() => setIsApprovalOpen(false)}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      <footer className="app-footer">
        <p>
          IncidentMind © 2026 — AI Incident Response Agent with Organizational Memory powered by Hindsight Cloud
        </p>
      </footer>
    </div>
  );
}

export default App;
