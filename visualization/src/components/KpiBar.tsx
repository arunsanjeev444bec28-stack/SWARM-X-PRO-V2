import React from 'react';

interface Props {
  racks: number;
  rfNodes: number;
  totalRobots: number;
  activeRobots: number;
  availableRobots?: number;
  faultRobots: number;
  activeTasks?: number;
  completedTasks?: number;
  routeDistanceM: number;
}

export function KpiBar({
  racks,
  rfNodes,
  totalRobots,
  activeRobots,
  availableRobots,
  faultRobots,
  activeTasks = 0,
  completedTasks = 0,
  routeDistanceM,
}: Props) {
  const avail = availableRobots !== undefined ? availableRobots : Math.max(0, totalRobots - activeRobots - faultRobots);

  return (
    <div className="kpi-bar" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
      <div className="kpi-item">
        <div className="kpi-label">Warehouse Racks</div>
        <div className="kpi-value">{racks}</div>
        <div className="kpi-sub">78 Shelving Bays (13×6)</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">RF Nodes</div>
        <div className="kpi-value active">{rfNodes}</div>
        <div className="kpi-sub">98 Aisle Intersections</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Total AMRs</div>
        <div className="kpi-value">{totalRobots}</div>
        <div className="kpi-sub">4 Corner Edge Agents</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Active AMRs</div>
        <div className={`kpi-value ${activeRobots > 0 ? 'active' : ''}`}>{activeRobots}</div>
        <div className="kpi-sub">Executing Missions</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Available AMRs</div>
        <div className="kpi-value ok">{avail}</div>
        <div className="kpi-sub">Ready to Bid</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Fleet Faults</div>
        <div className={`kpi-value ${faultRobots > 0 ? 'fault' : 'ok'}`}>{faultRobots}</div>
        <div className="kpi-sub">{faultRobots > 0 ? `${faultRobots} AMR Error` : '0 Faults (Healthy)'}</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Active Tasks</div>
        <div className={`kpi-value ${activeTasks > 0 ? 'active' : ''}`}>{activeTasks}</div>
        <div className="kpi-sub">In Dispatch / Route</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Completed Tasks</div>
        <div className="kpi-value ok">{completedTasks}</div>
        <div className="kpi-sub">Delivered Missions</div>
      </div>
      <div className="kpi-item">
        <div className="kpi-label">Mission Distance</div>
        <div className="kpi-value" style={{ color: 'var(--accent)' }}>
          {routeDistanceM > 0 ? `${routeDistanceM.toFixed(2)} m` : '0.00 m'}
        </div>
        <div className="kpi-sub">Actual A* RF Route</div>
      </div>
    </div>
  );
}
