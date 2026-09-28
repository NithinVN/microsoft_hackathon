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

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export async function fetchHealth(): Promise<HealthCheckResponse> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
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
