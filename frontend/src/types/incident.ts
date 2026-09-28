export type IncidentSeverity = 'SEV-1' | 'SEV-2' | 'SEV-3' | 'SEV-4';
export type IncidentStatus = 
  | 'DETECTED' 
  | 'INVESTIGATING' 
  | 'ANALYZING_BLAST_RADIUS' 
  | 'RETRIEVING_MEMORY' 
  | 'DIAGNOSING' 
  | 'WHAT_IF_ANALYSIS' 
  | 'AWAITING_APPROVAL' 
  | 'REMEDIATING' 
  | 'VERIFYING' 
  | 'RESOLVED' 
  | 'POSTMORTEM_SAVED';

export type ProductLoopStep = 
  | 'incident'
  | 'investigation'
  | 'blast_radius'
  | 'memory_recall'
  | 'diagnosis'
  | 'what_if'
  | 'approval'
  | 'remediation'
  | 'verification'
  | 'postmortem'
  | 'memory_retain';

export interface TelemetryMetric {
  timestamp: string;
  value: number;
  label: string;
}

export interface CurrentEvidence {
  telemetrySummary: string;
  metrics: {
    cpuUsage: TelemetryMetric[];
    errorRate: TelemetryMetric[];
    latencyMs: TelemetryMetric[];
  };
  liveLogs: string[];
  traces: {
    traceId: string;
    rootService: string;
    failingSpan: string;
    durationMs: number;
    httpStatus: number;
  }[];
}

export interface HistoricalEvidence {
  hindsightIncidentId: string;
  title: string;
  occurrenceDate: string;
  similarityScore: number;
  pastRootCause: string;
  attemptedFixes: {
    action: string;
    outcome: 'SUCCESS' | 'FAILURE';
    consequence: string;
    engineerNotes: string;
  }[];
  hindsightReflection: string;
}

export interface IncidentMemorySource {
  memory_id: string;
  service: string;
  content: string;
  classification: string;
  source: string;
  type: string;
  supporting_evidence: string[];
}

export interface IncidentMemoryResult {
  similar_incidents: Array<Record<string, any>>;
  historical_root_causes: Array<Record<string, any>>;
  successful_fixes: Array<Record<string, any>>;
  failed_fixes: Array<Record<string, any>>;
  engineer_lessons: Array<Record<string, any>>;
  historical_patterns: Array<Record<string, any>>;
  memory_confidence: number;
  memory_sources: IncidentMemorySource[];
}

export interface DocumentationEvidence {
  runbookTitle: string;
  docUrl: string;
  matchedSection: string;
  snippet: string;
  lastUpdated: string;
}

export interface AIInferenceEvidence {
  confidence: number;
  rootCauseHypothesis: string;
  chainOfThought: string[];
  recommendedFixId: string;
  riskAssessment: string;
}

export interface BlastRadiusNode {
  id: string;
  name: string;
  status: 'HEALTHY' | 'DEGRADED' | 'OUTAGE';
  type: 'GATEWAY' | 'SERVICE' | 'DATABASE' | 'CACHE' | 'QUEUE';
  latency: string;
  errorRate: string;
  affected: boolean;
}

export interface BlastRadiusLink {
  source: string;
  target: string;
  trafficRps: number;
  healthy: boolean;
}

export interface BlastRadiusData {
  rootService: string;
  affectedServicesCount: number;
  estimatedUserImpactPct: number;
  tier1Impact: boolean;
  nodes: BlastRadiusNode[];
  links: BlastRadiusLink[];
}

export interface AgentExecutionState {
  id: string;
  name: string;
  role: string;
  status: 'IDLE' | 'RUNNING' | 'COMPLETED' | 'WAITING_HUMAN' | 'FAILED';
  durationMs?: number;
  summary?: string;
  icon: string;
}

export interface CandidateRemediation {
  id: string;
  actionName: string;
  description: string;
  commandPreview: string; // Vetted pre-approved action (not arbitrary shell)
  safetyLevel: 'HIGH_RISK' | 'MEDIUM_RISK' | 'SAFE';
  historicalPrecedent: 'FAILED_BEFORE' | 'SUCCESS_BEFORE' | 'UNTESTED';
  historicalContext: string;
  predictedImpact: string;
  isRecommended: boolean;
}

export interface FailedFixWarning {
  dangerousAction: string;
  incidentRef: string;
  reason: string;
  historicalConsequence: string;
}

export interface PostmortemData {
  incidentId: string;
  title: string;
  durationMinutes: number;
  severity: IncidentSeverity;
  rootCause: string;
  detectionSource: string;
  timeline: { time: string; event: string }[];
  correctiveActions: string[];
  engineerFeedback?: string;
  engineerRating?: number;
  retainedToHindsight: boolean;
  hindsightMemoryId?: string;
}

export interface IncidentScenario {
  id: string;
  title: string;
  severity: IncidentSeverity;
  service: string;
  environment: string;
  status: IncidentStatus;
  startedAt: string;
  summary: string;
  currentEvidence: CurrentEvidence;
  historicalEvidence: HistoricalEvidence[];
  documentation: DocumentationEvidence[];
  aiInference: AIInferenceEvidence;
  blastRadius: BlastRadiusData;
  candidates: CandidateRemediation[];
  failedFixWarning?: FailedFixWarning;
  postmortem: PostmortemData;
}
