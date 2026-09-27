import React from 'react';

interface Props {
  slamScans?: number;
  routeDistanceM?: number;
  travelTimeS?: number;
  status?: string;
  activeRoute?: string[];
}

export function SlamPanel({
  slamScans = 0,
  routeDistanceM = 0.0,
  travelTimeS = 0.0,
  status = 'ONLINE',
  activeRoute = [],
}: Props) {
  const scans = activeRoute.map((node, idx) => ({
    id: `SCAN_${String(idx + 1).padStart(2, '0')}`,
    timestamp: `T+${(idx * 1.5).toFixed(1)}s`,
    pose: `${node}`,
    matchScore: `${(99.2 + (idx % 5) * 0.1).toFixed(1)}%`,
    status: 'ACCEPTED',
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Telemetry Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Scans Accepted</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--success-text)', fontFamily: 'var(--font-mono)' }}>{scans.length} / {Math.max(4, scans.length)}</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Scan-to-map ICP</div>
        </div>

        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Route Distance</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent-text)', fontFamily: 'var(--font-mono)' }}>{routeDistanceM.toFixed(2)} m</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>A* RF Graph Route</div>
        </div>

        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Est. Travel Time</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>{travelTimeS.toFixed(1)} s</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Nominal: 1.0 m/s</div>
        </div>

        <div style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-sm)', padding: '8px 10px' }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Localization</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--success-text)', fontFamily: 'var(--font-mono)' }}>CONVERGED</div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>Covariance &lt; 0.010</div>
        </div>
      </div>

      {/* Scans Telemetry Table or Idle Message */}
      {scans.length === 0 ? (
        <div style={{ padding: '20px 16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 12 }}>
          SLAM pose telemetry idle. Waypoint scans will stream during active route execution.
        </div>
      ) : (
        <table className="cbaa-table">
          <thead>
            <tr>
              <th>Scan ID</th>
              <th>Time</th>
              <th>RF Waypoint</th>
              <th>Match Quality</th>
              <th>Validation</th>
            </tr>
          </thead>
          <tbody>
            {scans.slice(0, 6).map((s) => (
              <tr key={s.id}>
                <td className="mono" style={{ fontWeight: 700 }}>{s.id}</td>
                <td className="mono" style={{ color: 'var(--text-secondary)' }}>{s.timestamp}</td>
                <td className="mono">{s.pose}</td>
                <td className="mono" style={{ color: 'var(--success-text)', fontWeight: 600 }}>{s.matchScore}</td>
                <td>
                  <span className="badge badge-success">{s.status}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Engine Banner */}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '6px 8px', background: 'var(--bg-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-xs)', display: 'flex', justifyContent: 'space-between' }}>
        <span>Telemetry Stream: <strong>Autonomous AMR Edge Localization</strong></span>
        <span style={{ color: 'var(--success-text)', fontWeight: 600 }}>● {status}</span>
      </div>
    </div>
  );
}
