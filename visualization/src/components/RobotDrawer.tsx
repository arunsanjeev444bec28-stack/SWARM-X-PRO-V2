import React from 'react';
import type { BackendRobot } from '../types/backend';

interface Props {
  robot: BackendRobot;
  task?: string;
  route?: string[];
  onClose: () => void;
}

function BarWidget({ value, max = 100 }: { value: number; max?: number }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const cls = pct > 50 ? 'bar-ok' : pct > 20 ? 'bar-warning' : 'bar-fault';
  return (
    <div className="bar-wrap">
      <div className="bar-track">
        <div className={`bar-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="bar-label">{value.toFixed(0)}%</span>
    </div>
  );
}

function getStatusBadge(status: string) {
  if (status === 'DEAD' || status === 'FAULT') return 'badge badge-fault';
  if (status === 'ACTIVE' || status === 'EXECUTING') return 'badge badge-active';
  if (status === 'IDLE' || status === 'AVAILABLE') return 'badge badge-success';
  return 'badge badge-neutral';
}

const ROBOT_POSITIONS: Record<string, string> = {
  R1: '[-6.0, -5.0, 0.12]',
  R2: '[-2.0, -5.0, 0.12]',
  R3: '[4.0, 7.0, 0.12]',
  R4: '[6.0, 9.0, 0.12]',
};

export function RobotDrawer({ robot, task, route, onClose }: Props) {
  const rid = robot.robot_id;
  const isFault = robot.status === 'DEAD' || robot.status === 'FAULT';
  const defaultRoute = rid === 'R2' ? ['RF_2_2', 'RF_2_3', 'RF_1_3', 'RF_1_4'] : [];
  const displayRoute = route && route.length > 0 ? route : defaultRoute;

  return (
    <>
      <div className="drawer-overlay" onClick={onClose} />
      <aside className="robot-drawer">
        <div className="drawer-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span className="mono" style={{ fontSize: 16, fontWeight: 700 }}>{rid}</span>
              <span className={getStatusBadge(robot.status)}>{robot.status}</span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>AMR Detail View</div>
          </div>
          <button className="drawer-close" onClick={onClose} title="Close">✕</button>
        </div>

        <div className="drawer-body">
          {/* Location */}
          <div className="drawer-section">
            <div className="drawer-section-title">Location</div>
            <div className="drawer-field">
              <span className="drawer-field-label">Current Node</span>
              <span className="drawer-field-val">{robot.node_id}</span>
            </div>
            <div className="drawer-field">
              <span className="drawer-field-label">Position (xyz)</span>
              <span className="drawer-field-val" style={{ fontSize: 10 }}>
                {ROBOT_POSITIONS[rid] ?? '—'}
              </span>
            </div>
          </div>

          {/* Mission */}
          <div className="drawer-section">
            <div className="drawer-section-title">Mission</div>
            <div className="drawer-field">
              <span className="drawer-field-label">Task</span>
              <span className="drawer-field-val">{task || (isFault ? '— (REVOKED)' : '—')}</span>
            </div>
            {displayRoute.length > 0 && (
              <div className="drawer-field" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 4 }}>
                <span className="drawer-field-label">Route</span>
                <div className="route-path" style={{ marginTop: 2 }}>
                  {displayRoute.map((node, i) => (
                    <React.Fragment key={node}>
                      <span>{node}</span>
                      {i < displayRoute.length - 1 && <span className="route-arrow">→</span>}
                    </React.Fragment>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Telemetry */}
          <div className="drawer-section">
            <div className="drawer-section-title">Telemetry</div>
            <div className="drawer-field">
              <span className="drawer-field-label">Battery</span>
              <BarWidget value={robot.battery} />
            </div>
            <div className="drawer-field">
              <span className="drawer-field-label">Health</span>
              <BarWidget value={robot.health} />
            </div>
            <div className="drawer-field">
              <span className="drawer-field-label">Temperature</span>
              <span className="drawer-field-val">{robot.temperature.toFixed(1)} °C</span>
            </div>
          </div>

          {/* Fault detail */}
          {isFault && (
            <div style={{
              background: 'var(--fault-bg)',
              border: '1px solid var(--fault-border)',
              borderRadius: 'var(--r-sm)',
              padding: '10px 12px',
            }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--fault)', marginBottom: 4 }}>
                ✕ FAULT CONDITION
              </div>
              <div style={{ fontSize: 11, color: 'var(--fault-text)' }}>
                Heartbeat timeout (&gt;2.0 s) detected at node {robot.node_id}. Robot disqualified from active fleet.
              </div>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
