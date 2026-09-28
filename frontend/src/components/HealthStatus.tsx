import React from 'react';
import { HealthCheckResponse } from '../api/client';
import { CheckCircle2, XCircle, AlertCircle, RefreshCw, Cpu, Brain, Database } from 'lucide-react';

interface HealthStatusProps {
  health: HealthCheckResponse | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export const HealthStatus: React.FC<HealthStatusProps> = ({
  health,
  loading,
  error,
  onRefresh,
}) => {
  return (
    <div className="card">
      <div className="card-header">
        <div className="flex-row">
          <div className="status-badge-container">
            {loading ? (
              <RefreshCw className="spin text-blue" size={20} />
            ) : error ? (
              <XCircle className="text-red" size={20} />
            ) : (
              <CheckCircle2 className="text-green" size={20} />
            )}
            <h2 className="card-title">Backend Connectivity Status</h2>
          </div>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="btn-secondary"
            title="Refresh Health Status"
          >
            <RefreshCw className={loading ? 'spin' : ''} size={16} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      <div className="card-body">
        {error ? (
          <div className="alert alert-error">
            <AlertCircle size={18} />
            <div>
              <strong>Failed to connect to backend:</strong> {error}
              <div className="text-muted text-sm mt-1">
                Make sure the backend is running on <code>http://127.0.0.1:8000</code>.
              </div>
            </div>
          </div>
        ) : health ? (
          <div className="grid-subsystems">
            <div className="subsystem-box">
              <div className="subsystem-header">
                <span className="dot dot-green"></span>
                <span className="subsystem-title">API Gateway</span>
              </div>
              <p className="subsystem-value">{health.status.toUpperCase()}</p>
              <span className="subsystem-meta">v{health.version} ({health.environment})</span>
            </div>

            <div className="subsystem-box">
              <div className="subsystem-header">
                <Cpu size={16} className="text-purple" />
                <span className="subsystem-title">LLM Target</span>
              </div>
              <p className="subsystem-value text-sm truncate">{health.services.model_configured}</p>
              <span className="subsystem-meta">Groq API Provider</span>
            </div>

            <div className="subsystem-box">
              <div className="subsystem-header">
                <Brain size={16} className="text-indigo" />
                <span className="subsystem-title">Hindsight Memory</span>
              </div>
              <p className="subsystem-value">
                {health.services.hindsight_configured ? (
                  <span className="text-green">Configured</span>
                ) : (
                  <span className="text-amber">Pending Key</span>
                )}
              </p>
              <span className="subsystem-meta">Cloud Org Experience</span>
            </div>

            <div className="subsystem-box">
              <div className="subsystem-header">
                <Database size={16} className="text-blue" />
                <span className="subsystem-title">App Database</span>
              </div>
              <p className="subsystem-value">
                {health.services.database_url_configured ? (
                  <span className="text-green">Configured</span>
                ) : (
                  <span className="text-red">Not Set</span>
                )}
              </p>
              <span className="subsystem-meta">State & Audit Store</span>
            </div>
          </div>
        ) : (
          <div className="text-muted">No status received yet.</div>
        )}

        {health && (
          <div className="timestamp-footer">
            <span>Last checked: {new Date(health.timestamp).toLocaleTimeString()}</span>
            <span>API Prefix: <code>/api/v1</code></span>
          </div>
        )}
      </div>
    </div>
  );
};
