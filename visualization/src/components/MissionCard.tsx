import React from 'react';
import type { CBAAAllocation } from '../types/backend';

interface Props {
  allocation?: CBAAAllocation;
  activeTask?: {
    task_id?: string;
    pickup_node?: string;
    dispatch_node?: string;
    status?: string;
    winner?: string;
    pickup?: string;
    destination?: string;
  };
  activeRoute?: string[];
  robotStatus?: string;
  progressPercent?: number;
}

export function MissionCard({
  allocation,
  activeTask,
  activeRoute = [],
  robotStatus = 'AVAILABLE',
  progressPercent = 0,
}: Props) {
  const taskId = activeTask?.task_id || allocation?.task_id;
  const winner = activeTask?.winner || allocation?.winner;
  const pickup = activeTask?.pickup_node || activeTask?.pickup;
  const dest = activeTask?.dispatch_node || activeTask?.destination;
  const status = activeTask?.status || (progressPercent >= 100 ? 'COMPLETED' : winner ? 'IN_PROGRESS' : 'IDLE');

  if (!taskId) {
    return (
      <div className="mission-card" style={{ padding: '24px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
          NO ACTIVE MISSION
        </div>
        <div style={{ fontSize: 13 }}>
          Warehouse fleet is currently standby. Enter and create a task from the Tasks panel to initiate live decentralized CBAA bidding and autonomous AMR execution.
        </div>
      </div>
    );
  }

  const isCompleted = status === 'COMPLETED';

  return (
    <div className="mission-card">
      {/* Mission Header */}
      <div
        className="panel-header"
        style={{
          background: 'var(--accent-subtle)',
          borderColor: 'var(--accent-border)',
          padding: '14px 18px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="panel-title" style={{ color: 'var(--accent-text)', fontSize: 16 }}>
            MISSION STATUS
          </span>
          <span className="mono mission-id">{taskId}</span>
        </div>
        <span
          className={`badge ${isCompleted ? 'badge-success' : 'badge-warning'}`}
          style={{ fontSize: 13, padding: '5px 12px' }}
        >
          {isCompleted ? '✓ COMPLETED' : '⚡ IN PROGRESS'}
        </span>
      </div>

      {/* Progress Bar */}
      <div style={{ padding: '12px 18px 0', background: 'var(--bg-surface)' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            fontSize: 13,
            fontWeight: 700,
            marginBottom: 6,
            color: 'var(--text-secondary)',
          }}
        >
          <span>Execution Progress</span>
          <span className="mono">{progressPercent.toFixed(0)}%</span>
        </div>
        <div style={{ height: 10, background: 'var(--border-medium)', borderRadius: 5, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${Math.min(100, Math.max(0, progressPercent))}%`,
              background: isCompleted ? 'var(--success)' : 'var(--accent)',
              borderRadius: 5,
              transition: 'width 0.4s ease-out',
            }}
          />
        </div>
      </div>

      {/* Mission Fields Grid */}
      <div className="mission-grid" style={{ padding: '16px 18px' }}>
        <div className="mission-field">
          <label style={{ fontSize: 13, fontWeight: 700 }}>Pickup Location</label>
          <span className="val" style={{ fontSize: 16, color: 'var(--warning-text)' }}>
            📦 {pickup || '—'}
          </span>
        </div>
        <div className="mission-field">
          <label style={{ fontSize: 13, fontWeight: 700 }}>Target Destination</label>
          <span className="val" style={{ fontSize: 16, color: 'var(--success-text)' }}>
            🎯 {dest || '—'}
          </span>
        </div>
        <div className="mission-field">
          <label style={{ fontSize: 13, fontWeight: 700 }}>Assigned Edge AMR</label>
          <span className="val" style={{ fontSize: 16, color: 'var(--accent)' }}>
            🤖 {winner || 'Bidding...'} ({robotStatus})
          </span>
        </div>
        <div className="mission-field">
          <label style={{ fontSize: 13, fontWeight: 700 }}>Consensus Auction Rule</label>
          <span className="val" style={{ fontSize: 14 }}>
            MINIMUM VALID BID
          </span>
        </div>
      </div>

      {/* Planned A* Route preview if available */}
      {activeRoute.length > 0 && (
        <div style={{ padding: '0 18px 14px', fontSize: 12 }}>
          <span style={{ fontWeight: 700, color: 'var(--text-secondary)' }}>Calculated RF Route: </span>
          <span className="mono" style={{ color: 'var(--accent-text)', wordBreak: 'break-all' }}>
            {activeRoute.join(' → ')}
          </span>
        </div>
      )}
    </div>
  );
}
