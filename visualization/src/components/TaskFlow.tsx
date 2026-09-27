import React from 'react';

interface Props {
  taskId?: string;
  originalRobot?: string;
  recoveryRobot?: string;
  failedNode?: string;
  pickup?: string;
  destination?: string;
  route?: string[];
  status?: string;
}

export function TaskFlow({
  taskId = 'TASK_FAILOVER_01',
  originalRobot = 'R1',
  recoveryRobot = 'R2',
  failedNode = 'RF_1_2',
  pickup = 'RF_1_1',
  destination = 'RF_1_4',
  route = ['RF_2_2', 'RF_2_3', 'RF_1_3', 'RF_1_4'],
  status = 'COMPLETED',
}: Props) {
  const steps = [
    {
      num: 1,
      title: 'Initial Dispatch',
      desc: `${originalRobot} assigned to pickup at ${pickup}`,
      state: 'done',
      tag: 'ORIGINAL',
    },
    {
      num: 2,
      title: 'AMR Failure Detected',
      desc: `${originalRobot} heartbeat lost at ${failedNode} (status: DEAD)`,
      state: 'fault',
      tag: 'FAILED',
    },
    {
      num: 3,
      title: 'CBAA Consensus Re-Auction',
      desc: `${recoveryRobot} won consensus (cost 0.0944, R1 excluded)`,
      state: 'done',
      tag: 'AUCTION',
    },
    {
      num: 4,
      title: 'Recovery Route Complete',
      desc: `${recoveryRobot} navigated detour to ${destination}`,
      state: 'success',
      tag: 'DELIVERED',
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Progression timeline */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {steps.map((s) => (
          <div
            key={s.num}
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--r-sm)',
              background: s.state === 'fault' ? 'var(--fault-bg)' : s.state === 'success' ? 'var(--success-bg)' : 'var(--bg-subtle)',
              border: `1px solid ${s.state === 'fault' ? 'var(--fault-border)' : s.state === 'success' ? 'var(--success-border)' : 'var(--border-subtle)'}`,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>STEP {s.num}</span>
              <span
                className={`badge ${s.state === 'fault' ? 'badge-fault' : s.state === 'success' ? 'badge-success' : 'badge-neutral'}`}
                style={{ fontSize: 9 }}
              >
                {s.tag}
              </span>
            </div>
            <div style={{ fontSize: 12, fontWeight: 700, color: s.state === 'fault' ? 'var(--fault-text)' : s.state === 'success' ? 'var(--success-text)' : 'var(--text-primary)', marginBottom: 2 }}>
              {s.title}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.3 }}>
              {s.desc}
            </div>
          </div>
        ))}
      </div>

      {/* Route & Waypoint Chain */}
      <div style={{ padding: '10px 14px', background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)' }}>
        <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>
          A* Detour Trajectory Sequence ({recoveryRobot} Active Path)
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {route.map((node, idx) => (
            <React.Fragment key={node}>
              <span
                className="mono"
                style={{
                  padding: '3px 8px',
                  borderRadius: 3,
                  fontSize: 11,
                  fontWeight: 600,
                  background: idx === route.length - 1 ? 'var(--success-bg)' : idx === 0 ? 'var(--accent-subtle)' : 'var(--bg-surface)',
                  border: `1px solid ${idx === route.length - 1 ? 'var(--success-border)' : idx === 0 ? 'var(--accent-border)' : 'var(--border-medium)'}`,
                  color: idx === route.length - 1 ? 'var(--success-text)' : idx === 0 ? 'var(--accent-text)' : 'var(--text-primary)',
                }}
              >
                {node}
              </span>
              {idx < route.length - 1 && (
                <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>→</span>
              )}
            </React.Fragment>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-muted)' }}>
            Avoids obstacle at <strong>{failedNode}</strong> (R1)
          </span>
        </div>
      </div>
    </div>
  );
}
