import React, { useEffect, useState } from 'react';

interface Props {
  systemOnline: boolean;
  wsStatus: 'CONNECTED' | 'DISCONNECTED';
  meshCount: number;
  meshTotal: number;
  simRunning: boolean;
  onSync: () => void;
}

export function Header({ systemOnline, wsStatus, meshCount, meshTotal, simRunning, onSync }: Props) {
  const [now, setNow] = useState(() => new Date().toLocaleTimeString('en-GB'));

  useEffect(() => {
    const id = setInterval(() => setNow(new Date().toLocaleTimeString('en-GB')), 1000);
    return () => clearInterval(id);
  }, []);

  return (
    <header className="app-header">
      <div className="header-brand">
        <span className="header-brand-title">SWARM-X PRO V2</span>
        <span className="header-brand-sub">Autonomous Warehouse Fleet Control</span>
      </div>

      <div className="header-indicators">
        <span
          className={`status-pill ${systemOnline ? 'online' : 'offline'}`}
          title="Backend API"
        >
          <span className="dot" />
          {systemOnline ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}
        </span>

        <span
          className={`status-pill ${wsStatus === 'CONNECTED' ? 'online' : 'neutral'}`}
          title="WebSocket live feed"
        >
          <span className="dot" />
          WS {wsStatus === 'CONNECTED' ? 'LIVE' : 'DISCONNECTED'}
        </span>

        <span className="status-pill online" title="Edge mesh connectivity">
          <span className="dot" />
          EDGE MESH {meshCount}/{meshTotal}
        </span>

        <span
          className={`status-pill ${simRunning ? 'online' : 'neutral'}`}
          title="Simulation engine"
        >
          <span className="dot" />
          {simRunning ? 'SIMULATION ACTIVE' : 'SIMULATION IDLE'}
        </span>

        <button className="btn btn-sm btn-icon" onClick={onSync} title="Refresh data">
          ↻
        </button>

        <span className="header-time">{now}</span>
      </div>
    </header>
  );
}
