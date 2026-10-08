export interface HealthCheckResponse {
  status: string;
  app_name: string;
  environment: string;
  timestamp: string;
  version: string;
  services: {
    api: string;
    model_configured: string;
    hindsight_configured: boolean;
    groq_configured: boolean;
    database_url_configured: boolean;
    postgresql?: 'available' | 'unavailable';
  };
}

export interface ApiIncidentEvent {
  id: number;
  incident_id: number;
  event_type: string;
  timestamp: string;
  actor: string;
  message: string;
  payload: Record<string, any>;
}

export interface ApiIncident {
  id: number;
  incident_id: string;
  title: string;
  description: string;
  severity: string;
  status: string;
  source: string;
  affected_service: string;
  detected_at: string;
  resolved_at: string | null;
  metadata: Record<string, any>;
  events: ApiIncidentEvent[];
}

export interface IncidentMemoryResult {
  similar_incidents: Array<Record<string, any>>;
  historical_root_causes: Array<Record<string, any>>;
  successful_fixes: Array<Record<string, any>>;
  failed_fixes: Array<Record<string, any>>;
  engineer_lessons: Array<Record<string, any>>;
  historical_patterns: Array<Record<string, any>>;
  memory_confidence: number;
  memory_sources: Array<{
    memory_id: string;
    service: string;
    content: string;
    classification: string;
    source: string;
    type: string;
    supporting_evidence: string[];
  }>;
}

export interface HindsightMemoryRecord {
  id?: string | null;
  text: string;
  type: string;
  tags: string[];
  metadata: Record<string, unknown>;
  context?: string | null;
  score?: number | null;
  category?: string;
  source?: string;
}

export type OrganizationalMemoryCategory =
  | 'historical_incidents'
  | 'root_causes'
  | 'successful_fixes'
  | 'failed_fixes'
  | 'engineer_feedback'
  | 'postmortem_lessons';

export interface OrganizationalMemoryResult {
  current_incident: { incident_id: string; service: string; query: string };
  status: 'available' | 'empty' | 'unavailable';
  bank_id: string;
  health: { healthy: boolean; status: string; message?: string; [key: string]: unknown };
  categories: Record<OrganizationalMemoryCategory, HindsightMemoryRecord[]>;
  retrieved_memories: HindsightMemoryRecord[];
  agent_evidence: HindsightMemoryRecord[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export async function fetchHealth(): Promise<HealthCheckResponse> {
  const [response, readinessResponse] = await Promise.all([
    fetch(`${API_BASE_URL}/health`, { headers: { 'Accept': 'application/json' } }),
    fetch(`${API_BASE_URL}/health/ready`, { headers: { 'Accept': 'application/json' } }),
  ]);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  if (!readinessResponse.ok) throw new Error(`Database readiness could not be checked: ${readinessResponse.status}`);
  const [health, readiness] = await Promise.all([response.json(), readinessResponse.json()]);
  return { ...health, services: { ...health.services, postgresql: readiness.services?.postgresql } };
}

export async function fetchIncidents(params?: { status?: string; severity?: string }): Promise<ApiIncident[]> {
  const query = new URLSearchParams();
  if (params?.status) query.append('status', params.status);
  if (params?.severity) query.append('severity', params.severity);

  const response = await fetch(`${API_BASE_URL}/incidents?${query.toString()}`, {
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch incidents: ${response.statusText}`);
  }
  return response.json();
}

export async function getIncidentById(idOrIncidentId: string): Promise<ApiIncident> {
  const response = await fetch(`${API_BASE_URL}/incidents/${idOrIncidentId}`, {
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch incident ${idOrIncidentId}: ${response.statusText}`);
  }
  return response.json();
}

export async function retryIncidentAnalysis(idOrIncidentId: string): Promise<{
  incident_id: string;
  current_step: string;
  status: string;
  retryable?: boolean;
  warnings: string[];
  errors: string[];
}> {
  const response = await fetch(`${API_BASE_URL}/incidents/${encodeURIComponent(idOrIncidentId)}/orchestrate`, {
    method: 'POST',
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) throw new Error(`Incident analysis retry failed: ${response.statusText}`);
  return response.json();
}

export async function retainDemoOutcome(): Promise<{
  status: 'retained' | 'unavailable';
  retained: boolean;
  bank_id: string;
  message: string;
}> {
  const response = await fetch(`${API_BASE_URL}/incidents/demo/retain`, {
    method: 'POST',
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) throw new Error(`Hindsight demo retention failed: ${response.statusText}`);
  return response.json();
}

export async function createIncidentApi(payload: {
  incident_id: string;
  title: string;
  description?: string;
  severity: string;
  status?: string;
  source?: string;
  affected_service: string;
  metadata?: Record<string, any>;
}): Promise<ApiIncident> {
  const response = await fetch(`${API_BASE_URL}/incidents`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`Failed to create incident: ${response.statusText}`);
  }
  return response.json();
}

export async function getIncidentMemory(idOrIncidentId: string): Promise<IncidentMemoryResult> {
  const response = await fetch(`${API_BASE_URL}/incidents/${idOrIncidentId}/memory`, {
    headers: { 'Accept': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Hindsight memory for incident ${idOrIncidentId}: ${response.statusText}`);
  }

  return response.json();
}

export async function getOrganizationalMemory(params: {
  incidentId: string;
  service: string;
  query: string;
  signal?: AbortSignal;
}): Promise<OrganizationalMemoryResult> {
  const query = new URLSearchParams({
    incident_id: params.incidentId,
    service: params.service,
    query: params.query,
  });
  const response = await fetch(`${API_BASE_URL}/incidents/organizational-memory?${query.toString()}`, {
    headers: { 'Accept': 'application/json' },
    signal: params.signal,
  });

  if (!response.ok) {
    throw new Error(`Failed to retrieve organizational memory: ${response.statusText}`);
  }

  return response.json();
}

export interface ExternalWebsiteIntegration {
  id: number;
  name: string;
  base_url: string;
  health_url?: string | null;
  webhook_url?: string | null;
  service_name?: string | null;
  service_identifier?: string | null;
  integration_method: string;
  status: string;
  last_checked_at?: string | null;
  last_response_time_ms?: number | null;
  last_status_code?: number | null;
  last_error?: string | null;
  metadata_json: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ExternalWebsiteConnectionTestResult {
  integration_id: number;
  status: string;
  reachable: boolean;
  http_status_code?: number | null;
  response_time_ms?: number | null;
  timeout_seconds: number;
  endpoint: string;
  health_status?: string | null;
  health_payload?: Record<string, any> | null;
  last_checked_at: string;
  error?: string | null;
}

export interface ExternalWebsiteFlaw {
  flaw_id: string;
  title: string;
  category: string;
  severity: string;
  confidence: number;
  status: string;
  description: string;
  evidence: string[];
  affected_endpoint: string;
  observed_value: string;
  expected_value: string;
  impact: string;
  likely_cause: string;
  recommended_action: string;
}

export interface ExternalWebsiteScanResult {
  integration_id: number;
  service: string;
  overall_status: string;
  health_status: string;
  api_status: string;
  dependencies_status: string;
  database_status: string;
  http_status_code?: number | null;
  response_time_ms?: number | null;
  incident_id?: string | null;
  detected_flaws: ExternalWebsiteFlaw[];
  evidence_summary: string[];
  last_checked_at: string;
  raw_data: Record<string, any>;
}

export async function createWebsiteIntegration(payload: {
  name: string;
  base_url: string;
  health_url?: string;
  webhook_url?: string;
  service_name?: string;
  service_identifier?: string;
  integration_method?: string;
  api_key?: string;
}): Promise<ExternalWebsiteIntegration> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`Failed to create integration: ${response.statusText}`);
  }
  return response.json();
}

export async function listWebsiteIntegrations(): Promise<ExternalWebsiteIntegration[]> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to list integrations: ${response.statusText}`);
  }
  return response.json();
}

export async function getWebsiteIntegration(id: number): Promise<ExternalWebsiteIntegration> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites/${id}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!response.ok) {
    throw new Error(`Failed to get integration: ${response.statusText}`);
  }
  return response.json();
}

export async function testWebsiteIntegrationConnection(id: number, payload?: { api_key?: string }): Promise<ExternalWebsiteConnectionTestResult> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites/${id}/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify(payload ?? {}),
  });
  if (!response.ok) {
    throw new Error(`Failed to test integration: ${response.statusText}`);
  }
  return response.json();
}

export async function scanWebsiteIntegration(id: number): Promise<ExternalWebsiteScanResult> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites/${id}/scan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({ force_refresh: true }),
  });
  if (!response.ok) {
    throw new Error(`Failed to scan integration: ${response.statusText}`);
  }
  return response.json();
}

export async function deleteWebsiteIntegration(id: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/integrations/websites/${id}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`Failed to delete integration: ${response.statusText}`);
  }
}
