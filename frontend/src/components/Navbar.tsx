import React from 'react';
import { ShieldAlert, Sparkles, Cpu, Play, RotateCcw } from 'lucide-react';
import { IncidentScenario } from '../types/incident';

interface NavbarProps {
  scenarios: IncidentScenario[];
  activeScenario: IncidentScenario;
  onSelectScenario: (scenario: IncidentScenario) => void;
  onReset: () => void;
  onAutoPlay: () => void;
  isPlaying: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  scenarios,
  activeScenario,
  onSelectScenario,
  onReset,
  onAutoPlay,
  isPlaying,
}) => {
  return (
    <header className="navbar">
      <div className="navbar-left">
        <div className="brand-logo">
          <ShieldAlert size={24} className="text-blue" />
          <span className="brand-text">IncidentMind</span>
        </div>
        <div className="scenario-selector-container">
          <label className="scenario-label text-muted text-xs">ACTIVE INCIDENT:</label>
          <select
            className="scenario-select"
            value={activeScenario.id}
            onChange={(e) => {
              const selected = scenarios.find((s) => s.id === e.target.value);
              if (selected) onSelectScenario(selected);
            }}
          >
            {scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                [{s.severity}] {s.id} - {s.title}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="navbar-actions">
        <button
          className={`btn-action ${isPlaying ? 'btn-active' : ''}`}
          onClick={onAutoPlay}
          title="Auto-run full 10-step agent loop"
        >
          <Play size={15} />
          <span>{isPlaying ? 'Loop Running...' : 'Auto-Run Pipeline'}</span>
        </button>

        <button
          className="btn-action-ghost"
          onClick={onReset}
          title="Reset incident state"
        >
          <RotateCcw size={15} />
          <span>Reset</span>
        </button>

        <div className="status-pill-group">
          <div className="status-pill hindsight-pill" title="Hindsight Cloud Organizational Memory Layer Active">
            <Sparkles size={14} className="text-purple" />
            <span>Hindsight Active</span>
          </div>

          <div className="status-pill groq-pill" title="Groq Configured LLM (openai/gpt-oss-120b)">
            <Cpu size={14} className="text-blue" />
            <span>Groq · gpt-oss-120b</span>
          </div>
        </div>
      </div>
    </header>
  );
};
