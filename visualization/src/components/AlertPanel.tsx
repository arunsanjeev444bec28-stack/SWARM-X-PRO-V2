import React from 'react';

interface Alert {
  id: string;
  severity: 'fault' | 'warning' | 'success' | 'info';
  title: string;
  detail?: string;
  time?: string;
}

interface Props {
  eventLog: any[];
}

const SEVERITY_ICONS: Record<string, string> = {
  fault: '✕',
  warning: '⚠',
  success: '✓',
  info: 'ℹ',
};

function buildAlerts(eventLog: any[]): Alert[] {
  const alerts: Alert[] = [];

  eventLog.forEach((e, i) => {
    const evName = String(e.event || '').toUpperCase();
    let sev: Alert['severity'] | null = null;

    if (evName.includes('FAIL') || evName.includes('ERROR') || evName === 'HEARTBEAT_TIMEOUT') {
      sev = 'fault';
    } else if (evName.includes('CONFLICT') || evName.includes('WAITING') || evName.includes('WARNING')) {
      sev = 'warning';
    } else if (evName === 'TASK_COMPLETED' || evName === 'WINNER_SELECTED') {
      sev = 'success';
    } else if (evName === 'TASK_CREATED' || evName === 'ROBOT_STARTED') {
      sev = 'info';
    }

    if (sev) {
      alerts.push({
        id: `alert-${i}`,
        severity: sev,
        title: e.event ?? 'ALERT',
        detail: [e.task_id, e.robot_id, e.reason || e.detail || e.message].filter(Boolean).join(' · '),
        time: e.timestamp ? String(e.timestamp).slice(11, 19) : undefined,
      });
    }
  });

  return alerts.slice(0, 10);
}

export function AlertPanel({ eventLog }: Props) {
  const alerts = buildAlerts(eventLog);

  if (alerts.length === 0) {
    return (
      <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4 }}>
          NO SYSTEM ALERTS
        </div>
        <div style={{ fontSize: 12 }}>
          All 4 AMRs and warehouse nodes operating within nominal thresholds. Zero active faults.
        </div>
      </div>
    );
  }

  return (
    <div className="alert-panel">
      {alerts.map((a) => (
        <div key={a.id} className={`alert-card alert-${a.severity}`}>
          <div className="alert-icon-col">
            <span className={`alert-symbol ${a.severity}`}>{SEVERITY_ICONS[a.severity]}</span>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="alert-title">{a.title}</span>
              {a.time && <span className="mono alert-time">{a.time}</span>}
            </div>
            {a.detail && <div className="alert-detail">{a.detail}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
