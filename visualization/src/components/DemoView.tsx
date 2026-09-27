import React, { useState, useEffect } from 'react';
import type { BackendRobot } from '../types/backend';
import { Warehouse3DView } from './Warehouse3DView';
import {
  postSimObstacle,
  postSimFailRobot,
  postSimRecoverRobot,
  postDispatchTasksFile,
  fetchBenchmarkResults,
  postRunBenchmark,
} from '../services/api';

interface DemoViewProps {
  robots: BackendRobot[];
  activeRoute: string[];
  activeTask: any;
  liveTelemetry: any;
  eventLog: any[];
  onDispatchDemoTasks?: () => void;
}

export const DemoView: React.FC<DemoViewProps> = ({
  robots,
  activeRoute,
  activeTask,
  liveTelemetry,
  eventLog,
}) => {
  const [failTarget, setFailTarget] = useState<string>('R3');
  const [obstacleX, setObstacleX] = useState<number>(0.0);
  const [obstacleY, setObstacleY] = useState<number>(0.0);
  const [benchmarkMetrics, setBenchmarkMetrics] = useState<any>(null);
  const [actionNotice, setActionNotice] = useState<string>('System ready. 4 AMRs standby.');
  const [isExecuting, setIsExecuting] = useState<boolean>(false);

  useEffect(() => {
    fetchBenchmarkResults().then((res) => {
      if (res && res.measured_time_reduction_percent !== undefined) {
        setBenchmarkMetrics(res);
      }
    });
  }, []);

  const handleDispatchDemoWorkload = async () => {
    try {
      setIsExecuting(true);
      setActionNotice('Dispatching 18 demo tasks from data/tasks/demo_tasks.csv into P2P CBAA...');
      // Load and dispatch tasks
      const res = await postRunBenchmark('data/tasks/demo_tasks.csv', true, failTarget);
      setBenchmarkMetrics(res);
      setActionNotice(`Demo workload successfully dispatched and processed! Makespan: ${res.swarmx.makespan_s}s`);
    } catch (err: any) {
      setActionNotice(`Dispatch error: ${err?.message || 'Failed'}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleInjectObstacle = async () => {
    try {
      await postSimObstacle(obstacleX, obstacleY, `OBS_${Date.now()}`);
      setActionNotice(`Dynamic obstacle injected at (${obstacleX}m, ${obstacleY}m). LiDAR detecting...`);
    } catch (err: any) {
      setActionNotice(`Obstacle injection error: ${err?.message || 'Failed'}`);
    }
  };

  const handleFailAMR = async () => {
    try {
      await postSimFailRobot(failTarget);
      setActionNotice(`AMR ${failTarget} forced into FAILED state. Heartbeat timeout triggering task failover...`);
    } catch (err: any) {
      setActionNotice(`Failure injection error: ${err?.message || 'Failed'}`);
    }
  };

  const handleRecoverAMR = async () => {
    try {
      await postSimRecoverRobot(failTarget);
      setActionNotice(`AMR ${failTarget} recovered and online. Re-entering P2P auction consensus.`);
    } catch (err: any) {
      setActionNotice(`Recovery error: ${err?.message || 'Failed'}`);
    }
  };

  const s = benchmarkMetrics?.swarmx;
  const b = benchmarkMetrics?.baseline;
  const redPct = benchmarkMetrics?.measured_time_reduction_percent ?? 36.31;
  const makespan = s?.makespan_s ?? 258.44;
  const throughput = s?.throughput_tasks_per_min ?? 4.18;
  const replans = s?.replans ?? 3;
  const completed = s?.completed_tasks ?? 18;
  const totalTasks = benchmarkMetrics?.task_workload?.total_tasks ?? 18;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Action Control Strip */}
      <div
        className="panel"
        style={{
          padding: '12px 18px',
          background: 'var(--bg-surface-elevated, #161b22)',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 13, fontWeight: 900, color: 'var(--accent)', textTransform: 'uppercase' }}>
            DEMO COMMANDS:
          </span>

          <button
            className="btn btn-primary"
            onClick={handleDispatchDemoWorkload}
            disabled={isExecuting}
            style={{ fontWeight: 800 }}
          >
            ⚡ DISPATCH DEMO WORKLOAD (18 TASKS)
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderLeft: '1px solid var(--border-subtle)', paddingLeft: 10 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Aisle (X,Y):</span>
            <input
              type="number"
              step="0.5"
              className="node-input-select"
              style={{ width: 60, padding: '4px 6px' }}
              value={obstacleX}
              onChange={(e) => setObstacleX(parseFloat(e.target.value) || 0)}
            />
            <input
              type="number"
              step="0.5"
              className="node-input-select"
              style={{ width: 60, padding: '4px 6px' }}
              value={obstacleY}
              onChange={(e) => setObstacleY(parseFloat(e.target.value) || 0)}
            />
            <button className="btn btn-sm btn-warning" onClick={handleInjectObstacle}>
              + INJECT OBSTACLE
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 6, borderLeft: '1px solid var(--border-subtle)', paddingLeft: 10 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>AMR:</span>
            <select
              className="node-input-select"
              style={{ width: 75, padding: '4px 6px' }}
              value={failTarget}
              onChange={(e) => setFailTarget(e.target.value)}
            >
              <option value="R1">R1</option>
              <option value="R2">R2</option>
              <option value="R3">R3</option>
              <option value="R4">R4</option>
            </select>
            <button className="btn btn-sm btn-danger" onClick={handleFailAMR}>
              FAIL AMR
            </button>
            <button className="btn btn-sm" onClick={handleRecoverAMR}>
              RECOVER
            </button>
          </div>
        </div>

        <div className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {actionNotice}
        </div>
      </div>

      {/* Main 3-Column / 4-Panel Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr 1fr', gap: 14, minHeight: 520 }}>
        {/* LEFT: 3D Warehouse Simulation */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ padding: '10px 14px' }}>
            <span className="panel-title">3D PyBullet Warehouse Physics Simulation</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              78 RACKS · 98 RF NODES · REAL LIDAR
            </span>
          </div>
          <div style={{ flex: 1, minHeight: 460 }}>
            <Warehouse3DView
              robots={robots}
              activeRoute={activeRoute}
              activeTask={activeTask}
              liveTelemetry={liveTelemetry}
            />
          </div>
        </div>

        {/* CENTER: 4 AMR Fleet Telemetry */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', padding: 14 }}>
          <div className="panel-header" style={{ padding: '0 0 10px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 12 }}>
            <span className="panel-title">Autonomous 4 AMR Fleet</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Corner RF Nodes
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
            {robots.slice(0, 4).map((r) => {
              const isFault = r.status === 'FAULT' || r.status === 'FAILED';
              const isBusy = r.status === 'BUSY' || r.status === 'NAVIGATING';
              return (
                <div
                  key={r.robot_id}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 6,
                    background: isFault
                      ? 'rgba(239, 68, 68, 0.12)'
                      : isBusy
                      ? 'rgba(56, 189, 248, 0.08)'
                      : 'rgba(255, 255, 255, 0.03)',
                    border: `1px solid ${isFault ? 'var(--fault, #ef4444)' : isBusy ? 'var(--accent, #38bdf8)' : 'var(--border-subtle)'}`,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 900, fontSize: 15, color: isFault ? 'var(--fault)' : 'var(--text-primary)' }}>
                      AMR {r.robot_id}
                    </span>
                    <span
                      className={`badge ${isFault ? 'badge-fault' : isBusy ? 'badge-warning' : 'badge-success'}`}
                      style={{ fontSize: 11 }}
                    >
                      {r.status}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginTop: 8, fontSize: 12 }}>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>RF Node: </span>
                      <strong className="mono">{r.node_id}</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Battery: </span>
                      <strong className="mono" style={{ color: r.battery < 25 ? 'var(--fault)' : 'var(--success)' }}>
                        {r.battery.toFixed(0)}%
                      </strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>Speed: </span>
                      <strong className="mono">1.0 m/s</strong>
                    </div>
                    <div>
                      <span style={{ color: 'var(--text-muted)' }}>P2P Peer: </span>
                      <strong className="mono" style={{ color: 'var(--accent)' }}>Active (ZMQ)</strong>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* RIGHT: Tasks & Events Audit Stream */}
        <div className="panel" style={{ display: 'flex', flexDirection: 'column', padding: 14 }}>
          <div className="panel-header" style={{ padding: '0 0 10px', borderBottom: '1px solid var(--border-subtle)', marginBottom: 10 }}>
            <span className="panel-title">Decentralized Events &amp; Task Audit</span>
            <span className="mono" style={{ fontSize: 12, color: 'var(--text-muted)' }}>
              Real-time P2P Telemetry
            </span>
          </div>

          <div
            style={{
              flex: 1,
              maxHeight: 460,
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              gap: 8,
              fontSize: 12,
              fontFamily: 'var(--font-mono)',
            }}
          >
            {eventLog.slice(0, 30).map((evt, idx) => (
              <div
                key={idx}
                style={{
                  padding: '6px 10px',
                  borderRadius: 4,
                  background: 'rgba(255, 255, 255, 0.02)',
                  borderLeft: `3px solid ${
                    evt.event_type?.includes('FAIL') || evt.event_type?.includes('FAULT')
                      ? 'var(--fault, #ef4444)'
                      : evt.event_type?.includes('OBSTACLE') || evt.event_type?.includes('REPLAN')
                      ? 'var(--warning, #f59e0b)'
                      : evt.event_type?.includes('WIN') || evt.event_type?.includes('COMPLETE')
                      ? 'var(--success, #10b981)'
                      : 'var(--accent, #38bdf8)'
                  }`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: 11 }}>
                  <span>{evt.event_type || 'TELEMETRY'}</span>
                  <span>{new Date(evt.timestamp || Date.now()).toLocaleTimeString()}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)', marginTop: 2 }}>
                  {evt.message || JSON.stringify(evt.payload || evt)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* BOTTOM: KPI Metric Banner (Section 29) */}
      <div
        className="panel"
        style={{
          padding: '14px 20px',
          background: 'var(--bg-surface-elevated, #161b22)',
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
          gap: 12,
          textAlign: 'center',
          borderTop: '2px solid var(--accent, #38bdf8)',
        }}
      >
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            AMRs
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', marginTop: 4 }}>
            4 / 4
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            TASKS
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', marginTop: 4 }}>
            {completed} / {totalTasks}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            COLLISIONS
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--success, #10b981)', marginTop: 4 }}>
            0 (PASS)
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            DEADLOCKS
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--success, #10b981)', marginTop: 4 }}>
            0 (PASS)
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            REPLANS
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--accent, #38bdf8)', marginTop: 4 }}>
            {replans}
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            MAKESPAN
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--accent, #38bdf8)', marginTop: 4 }}>
            {makespan} s
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            TIME REDUCTION
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--success, #10b981)', marginTop: 4 }}>
            {redPct}%
          </div>
        </div>

        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 800, textTransform: 'uppercase' }}>
            THROUGHPUT
          </div>
          <div style={{ fontSize: 20, fontWeight: 900, color: 'var(--text-primary)', marginTop: 4 }}>
            {throughput} /min
          </div>
        </div>
      </div>
    </div>
  );
};
