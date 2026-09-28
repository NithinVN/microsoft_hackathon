import React from 'react';
import { BlastRadiusData } from '../types/incident';
import { Network, AlertOctagon, CheckCircle2, AlertTriangle, Users, Layers } from 'lucide-react';

interface BlastRadiusViewerProps {
  blastRadius: BlastRadiusData;
}

export const BlastRadiusViewer: React.FC<BlastRadiusViewerProps> = ({ blastRadius }) => {
  const getNodeColor = (status: string) => {
    switch (status) {
      case 'OUTAGE': return 'node-outage';
      case 'DEGRADED': return 'node-degraded';
      default: return 'node-healthy';
    }
  };

  return (
    <div className="card blast-radius-card">
      <div className="card-header flex-row">
        <div className="flex-row items-center gap-2">
          <Network size={18} className="text-amber" />
          <h3 className="card-title">Blast Radius & Service Dependency Analysis</h3>
        </div>
        <span className="text-xs text-muted">Blast Radius Agent Graph Evaluation</span>
      </div>

      <div className="card-body">
        {/* KPI Banner */}
        <div className="blast-kpi-row">
          <div className="blast-kpi-box">
            <span className="kpi-label">ROOT IMPACTED SERVICE</span>
            <span className="kpi-value text-red">{blastRadius.rootService}</span>
          </div>

          <div className="blast-kpi-box">
            <span className="kpi-label">AFFECTED SERVICES</span>
            <span className="kpi-value text-amber">{blastRadius.affectedServicesCount} of {blastRadius.nodes.length}</span>
          </div>

          <div className="blast-kpi-box">
            <span className="kpi-label">ESTIMATED USER IMPACT</span>
            <span className="kpi-value text-red">
              <Users size={16} className="inline-icon" /> {blastRadius.estimatedUserImpactPct}% of Traffic
            </span>
          </div>

          <div className="blast-kpi-box">
            <span className="kpi-label">TIER-1 EXPOSURE</span>
            <span className="kpi-value text-purple">
              <AlertOctagon size={16} className="inline-icon" /> {blastRadius.tier1Impact ? 'CRITICAL (Tier-1)' : 'Standard'}
            </span>
          </div>
        </div>

        {/* Visual Topology Diagram */}
        <div className="topology-canvas">
          <div className="topology-title-bar">
            <span>SERVICE DEPENDENCY MESH</span>
            <div className="topology-legend">
              <span className="legend-item"><span className="legend-dot dot-red"></span> Outage</span>
              <span className="legend-item"><span className="legend-dot dot-amber"></span> Degraded</span>
              <span className="legend-item"><span className="legend-dot dot-green"></span> Normal</span>
            </div>
          </div>

          <div className="nodes-layout-grid">
            {blastRadius.nodes.map((node) => (
              <div key={node.id} className={`topology-node-card ${getNodeColor(node.status)}`}>
                <div className="node-card-top">
                  <div className="flex-row items-center gap-2">
                    <Layers size={14} />
                    <span className="node-name">{node.name}</span>
                  </div>
                  <span className={`node-status-tag status-${node.status.toLowerCase()}`}>
                    {node.status === 'OUTAGE' ? (
                      <AlertOctagon size={12} />
                    ) : node.status === 'DEGRADED' ? (
                      <AlertTriangle size={12} />
                    ) : (
                      <CheckCircle2 size={12} />
                    )}
                    {node.status}
                  </span>
                </div>

                <div className="node-stats">
                  <div>Type: <strong>{node.type}</strong></div>
                  <div>Latency: <strong className={node.affected ? 'text-red' : 'text-green'}>{node.latency}</strong></div>
                  <div>Error Rate: <strong className={node.affected ? 'text-red' : 'text-green'}>{node.errorRate}</strong></div>
                </div>
              </div>
            ))}
          </div>

          <div className="links-summary-box">
            <span className="box-sublabel">ACTIVE SERVICE CALL PATHS:</span>
            <div className="links-pills">
              {blastRadius.links.map((link, lidx) => (
                <div key={lidx} className={`link-pill ${link.healthy ? 'link-ok' : 'link-bad'}`}>
                  <span>{link.source}</span>
                  <span className="link-arrow">→</span>
                  <span>{link.target}</span>
                  <span className="link-rps">({link.trafficRps} rps)</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
