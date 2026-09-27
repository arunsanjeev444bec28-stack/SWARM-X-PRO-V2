import React, { useState } from 'react';
import type { BackendRobot, CBAAAllocation, BackendPath } from '../types/backend';
import { RobotDrawer } from './RobotDrawer';

interface Props {
  robots: BackendRobot[];
  allocations: CBAAAllocation[];
  paths: BackendPath[];
}

function barCls(v: number) {
  return v > 50 ? 'bar-ok' : v > 20 ? 'bar-warning' : 'bar-fault';
}

function statusBadgeCls(status: string) {
  const s = (status || '').toUpperCase();
  if (s === 'DEAD' || s === 'FAULT' || s === 'FAILED') return 'badge-fault';
  if (s === 'ACTIVE' || s === 'MOVING' || s === 'DISPATCHING' || s === 'TRANSPORTING') return 'badge-active';
  if (s === 'LOADING') return 'badge-warning';
  if (s === 'IDLE' || s === 'AVAILABLE' || s === 'COMPLETED') return 'badge-success';
  return 'badge-neutral';
}

function statusLabel(status: string): string {
  const s = (status || '').toUpperCase();
  const map: Record<string, string> = {
    DEAD: 'FAULT',
    FAULT: 'FAULT',
    FAILED: 'FAULT',
    ACTIVE: 'ACTIVE',
    MOVING: 'MOVING',
    DISPATCHING: 'DISPATCHING',
    TRANSPORTING: 'TRANSPORTING',
    LOADING: 'LOADING',
    IDLE: 'AVAILABLE',
    AVAILABLE: 'AVAILABLE',
    COMPLETED: 'COMPLETED',
  };
  return map[s] ?? s;
}

const DEFAULT_FLEET: BackendRobot[] = [
  { robot_id: 'R1', node_id: 'RF_6_0', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R2', node_id: 'RF_6_13', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R3', node_id: 'RF_0_0', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R4', node_id: 'RF_0_13', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
];

export function FleetTable({ robots, allocations, paths }: Props) {
  const [selectedRobot, setSelectedRobot] = useState<BackendRobot | null>(null);

  const displayRobots = robots && robots.length >= 4 ? robots : DEFAULT_FLEET;

  function getTask(rid: string): string {
    const alloc = allocations.find((a) => a.winner === rid);
    return alloc?.task_id || '—';
  }

  function getRoute(rid: string): string[] {
    const p = paths.find((p) => p.robot_id === rid);
    return p?.path ?? [];
  }

  return (
    <>
      <div className="panel-body-compact scroll-y">
        <table className="fleet-table">
          <thead>
            <tr>
              <th>AMR Unit</th>
              <th>Status</th>
              <th>Grid Node</th>
              <th>Active Mission</th>
              <th>Battery Margin</th>
              <th>Hardware Health</th>
            </tr>
          </thead>
          <tbody>
            {displayRobots.map((r) => {
              const isFault = r.status === 'DEAD' || r.status === 'FAULT' || r.status === 'FAILED';
              return (
                <tr
                  key={r.robot_id}
                  className={isFault ? 'fault-row' : ''}
                  onClick={() => setSelectedRobot(r)}
                  title={`Click to inspect telemetry for ${r.robot_id}`}
                >
                  <td>
                    <span
                      className="mono"
                      style={{
                        fontWeight: 800,
                        fontSize: 15,
                        color: isFault ? 'var(--fault)' : 'var(--accent)',
                      }}
                    >
                      {r.robot_id}
                    </span>
                  </td>
                  <td>
                    <span
                      className={`badge ${statusBadgeCls(r.status)}`}
                      style={{ fontSize: 12, padding: '4px 10px' }}
                    >
                      {statusLabel(r.status)}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontWeight: 700, fontSize: 14 }}>
                      {r.node_id}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {getTask(r.robot_id)}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="battery-bar" style={{ width: 60 }}>
                        <div
                          className={`battery-fill ${barCls(r.battery)}`}
                          style={{ width: `${Math.min(100, Math.max(0, r.battery))}%` }}
                        />
                      </div>
                      <span className="mono" style={{ fontSize: 12, fontWeight: 700 }}>
                        {r.battery.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div className="battery-bar" style={{ width: 60 }}>
                        <div
                          className={`battery-fill ${barCls(r.health ?? 100)}`}
                          style={{ width: `${Math.min(100, Math.max(0, r.health ?? 100))}%` }}
                        />
                      </div>
                      <span className="mono" style={{ fontSize: 12, fontWeight: 700 }}>
                        {(r.health ?? 100).toFixed(0)}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedRobot && (
        <RobotDrawer
          robot={selectedRobot}
          route={getRoute(selectedRobot.robot_id)}
          onClose={() => setSelectedRobot(null)}
        />
      )}
    </>
  );
}
