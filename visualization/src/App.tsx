import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import * as XLSX from 'xlsx';
import {
  fetchHealth,
  fetchApiState,
  fetchMetrics,
  fetchTasks,
  fetchRobots,
  fetchWarehouse,
  fetchAllocations,
  fetchPaths,
  fetchReservations,
  fetchConflicts,
  fetchEvents,
  fetchConfig,
  fetchSimulationState,
  fetchSimulationWarehouse,
  postTask,
  postBatchTasks,
  connectWebSocket,
} from './services/api';
import type {
  BackendPath,
  BackendRobot,
  BackendTask,
  CBAAAllocation,
  ConflictRecord,
  DashboardSnapshot,
  SpaceTimeReservation,
  TaskRow,
  WarehouseNode,
  SimulationState,
  SimulationWarehouse,
  WarehouseData,
} from './types/backend';

// Components
import { Header }       from './components/Header';
import { KpiBar }       from './components/KpiBar';
import { WarehouseMap, DEFAULT_CORNER_ROBOTS, CORNER_RF_NODES } from './components/WarehouseMap';
import { FleetTable }   from './components/FleetTable';
import { RobotDrawer }  from './components/RobotDrawer';
import { MissionCard }  from './components/MissionCard';
import { CbaaPanel }    from './components/CbaaPanel';
import { AlertPanel }   from './components/AlertPanel';
import { EventFeed }    from './components/EventFeed';
import { SlamPanel }    from './components/SlamPanel';
import { Warehouse3DView } from './components/Warehouse3DView';
import { SlamView } from './components/SlamView';
import { PerformanceView } from './components/PerformanceView';
import { DemoView } from './components/DemoView';
import { TaskImportPanel } from './components/TaskImportPanel';
import {
  postSimObstacle,
  postSimFailRobot,
  postSimRecoverRobot,
} from './services/api';

// ─── Navigation ─────────────────────────────────────────────────────────────
const NAV_TABS = ['Overview', 'Demo', 'Fleet', 'Tasks', '3D Simulation', 'SLAM', 'Map', 'Performance', 'Events'] as const;
type NavTab = (typeof NAV_TABS)[number];

// 98 discrete RF grid nodes at aisle intersections (14 cols x 7 rows)
const ALL_RF_NODES: string[] = [];
for (let r = 0; r < 7; r++) {
  for (let c = 0; c < 14; c++) {
    ALL_RF_NODES.push(`RF_${r}_${c}`);
  }
}

export default function App() {
  const [tab, setTab]                     = useState<NavTab>('Overview');
  const [snapshot, setSnapshot]           = useState<DashboardSnapshot | null>(null);
  const [warehouseData, setWarehouseData] = useState<WarehouseData | null>(null);
  const [loading, setLoading]             = useState(true);
  const [backendError, setBackendError]   = useState<string | null>(null);
  const [wsStatus, setWsStatus]           = useState<'CONNECTED' | 'DISCONNECTED'>('DISCONNECTED');
  const [eventLog, setEventLog]           = useState<any[]>([]);
  const [actionMsg, setActionMsg]         = useState('');

  // Live Fleet State (Initially 4 corner AMRs, all AVAILABLE)
  const [liveRobots, setLiveRobots]       = useState<BackendRobot[]>(DEFAULT_CORNER_ROBOTS);

  // Active Task & Dynamic Route Execution (Initially zero tasks, zero fake missions)
  const [activeRoute, setActiveRoute]     = useState<string[]>([]);
  const [activeTask, setActiveTask]       = useState<any>(null);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [isDispatching, setIsDispatching] = useState<boolean>(false);

  // Real-time PyBullet Simulation and SLAM State
  const [liveSlamData, setLiveSlamData]   = useState<any>(null);
  const [liveTelemetry, setLiveTelemetry] = useState<any>(null);
  const [failTarget, setFailTarget]       = useState<string>('R1');
  const [obstacleX, setObstacleX]         = useState<number>(0.0);
  const [obstacleY, setObstacleY]         = useState<number>(0.0);

  // Operator Task Creation Form State
  const [taskForm, setTaskForm] = useState({
    task_id: '',
    pickup_node: 'RF_5_1',
    dispatch_node: 'RF_2_10',
    priority: 'NORMAL',
    task_type: 'TRANSPORT',
    deadline: '120',
  });

  // Settings / Batch import form state
  const [datasetPreview, setDatasetPreview] = useState<TaskRow[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stepTimerRef = useRef<any>(null);

  // ── Data fetch ────────────────────────────────────────────────────────────
  const refreshData = useCallback(async () => {
    try {
      const [state, health, metrics, tasks, robots, warehouse, allocations, conflicts, reservations, paths, events, config] =
        await Promise.all([
          fetchApiState(),
          fetchHealth(),
          fetchMetrics(),
          fetchTasks(),
          fetchRobots(),
          fetchWarehouse(),
          fetchAllocations(),
          fetchConflicts(),
          fetchReservations(),
          fetchPaths(),
          fetchEvents(),
          fetchConfig(),
        ]);

      if (warehouse && !Array.isArray(warehouse) && (warehouse as any).racks) {
        setWarehouseData(warehouse as WarehouseData);
      }

      if (robots && robots.length >= 4) {
        setLiveRobots(robots);
      }

      const merged: DashboardSnapshot = {
        state: state ?? {},
        health: health ?? { status: 'down' },
        metrics: metrics ?? {},
        tasks: tasks ?? [],
        robots: robots && robots.length >= 4 ? robots : DEFAULT_CORNER_ROBOTS,
        warehouse: Array.isArray(warehouse) ? warehouse : [],
        allocations: allocations ?? [],
        deadlocks: { active_deadlocks: [], dependency_graph: {}, total_deadlocks: 0, recovered_deadlocks: 0, failed_recoveries: 0 },
        conflicts: conflicts ?? [],
        reservations: reservations ?? [],
        paths: paths ?? [],
        congestion: [],
        obstacles: [],
        failures: [],
        aiStatus: {},
        aiMetrics: {},
        aiFeatures: {},
        config: config ?? undefined,
      };
      setSnapshot(merged);
      if (events?.length) setEventLog((prev) => [...events, ...prev].slice(0, 300));
      setBackendError(null);
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Backend connection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // ── WebSocket & Simulation State Polling ──────────────────────────────────
  useEffect(() => {
    refreshData();
    const ws = connectWebSocket((msg: any) => {
      setEventLog((prev) => [msg, ...prev].slice(0, 300));

      // Handle continuous physical simulation telemetry
      if (msg.event === 'SIMULATION_TELEMETRY') {
        setLiveTelemetry(msg);
        if (Array.isArray(msg.robots)) {
          setLiveRobots((prev) =>
            prev.map((r) => {
              const item = msg.robots.find((m: any) => m.robot_id === r.robot_id);
              if (!item) return r;
              return {
                ...r,
                node_id: item.current_node || r.node_id,
                position: [item.x, item.y, item.z !== undefined ? item.z : 0.12],
                yaw: item.yaw,
                speed: item.speed,
                status: item.status || r.status,
                battery: item.battery !== undefined ? item.battery : r.battery,
              };
            })
          );
        }
      }

      // Handle live SLAM map generation updates
      if (msg.event === 'SLAM_MAP_UPDATED' && msg.slam) {
        setLiveSlamData(msg.slam);
      }

      // Handle dynamic obstacle detection and replanning
      if (msg.event === 'OBSTACLE_DETECTED') {
        setActionMsg(`⚠ OBSTACLE DETECTED by AMR ${msg.robot_id} LiDAR! Triggering local A* replanning…`);
      }

      if (msg.event === 'DYNAMIC_REPLAN') {
        if (msg.new_route && msg.new_route.length > 0) {
          setActiveRoute(msg.new_route);
        }
        setActionMsg(`🔄 REPLANNING COMPLETE for AMR ${msg.robot_id}: New route calculated avoiding obstacle!`);
      }

      // Handle robot failure and task reallocation
      if (msg.event === 'ROBOT_FAILED') {
        setActionMsg(`❌ AMR ${msg.robot_id} REPORTED FAULT / STOPPED! Reopening mission for remaining AMRs…`);
        setLiveRobots((prev) =>
          prev.map((r) => (r.robot_id === msg.robot_id ? { ...r, status: 'FAULT', health: 0.0 } : r))
        );
      }

      if (msg.event === 'ROBOT_RECOVERED') {
        setActionMsg(`✓ AMR ${msg.robot_id} recovered from fault state. Now AVAILABLE.`);
        setLiveRobots((prev) =>
          prev.map((r) => (r.robot_id === msg.robot_id ? { ...r, status: 'AVAILABLE', health: 1.0 } : r))
        );
      }

      if (msg.event === 'TASK_REOPENED') {
        setActionMsg(`♻ Task ${msg.task_id} REOPENED! Surviving edge agents bidding in CBAA reauction…`);
      }

      // Handle collision / node arbitration events
      if (msg.event === 'NODE_ARBITRATION_WAIT') {
        setActionMsg(`⏸ AMR ${msg.waiting_robot} STOP & WAIT: Node ${msg.node_id} occupied by ${msg.occupying_robot}`);
      }

      if (msg.event === 'NODE_ARBITRATION_ENTER') {
        setActionMsg(`▶ AMR ${msg.robot_id} ENTER_NODE: Node ${msg.node_id} reserved and clear`);
      }

      // Handle real-time robot state updates from backend simulation / edge agents
      if (msg.event === 'ROBOT_STATE_UPDATED' && msg.robot_id) {
        setLiveRobots((prev) =>
          prev.map((r) =>
            r.robot_id === msg.robot_id
              ? {
                  ...r,
                  node_id: msg.node_id || r.node_id,
                  battery: msg.battery !== undefined ? msg.battery : r.battery,
                  health: msg.health !== undefined ? msg.health : r.health,
                  status: msg.status || r.status,
                  position: msg.x !== undefined && msg.y !== undefined ? [msg.x, msg.y, 0.12] : r.position,
                }
              : r
          )
        );
      }

      // Handle Task lifecycle events
      if (msg.event === 'WINNER_SELECTED' || msg.event === 'ROBOT_STARTED') {
        if (msg.route && msg.route.length > 0) {
          setActiveRoute(msg.route);
        }
        setActiveTask((prev: any) => ({
          ...(prev || {}),
          task_id: msg.task_id || prev?.task_id,
          winner: msg.winner || msg.robot_id || prev?.winner,
          status: 'IN_PROGRESS',
        }));
        setActionMsg(`✓ AMR ${msg.winner || msg.robot_id} moving along calculated A* RF route…`);
      }

      if (msg.event === 'PICKUP_REACHED') {
        setProgressPercent(50);
        setActionMsg(`📦 AMR ${msg.robot_id} arrived at pickup location for ${msg.task_id}. Loading payload…`);
      }

      if (msg.event === 'DISPATCH_REACHED' || msg.event === 'TASK_COMPLETED') {
        setProgressPercent(100);
        setActiveTask((prev: any) => ({
          ...(prev || {}),
          status: 'COMPLETED',
        }));
        setIsDispatching(false);
        setActionMsg(`🎉 Task ${msg.task_id} successfully delivered! AMR returning to available standby.`);
        refreshData();
      }

      if (['TASK_CREATED', 'TASK_ASSIGNED', 'PATH_PLANNED', 'RESERVATION_CREATED', 'CONFLICT_DETECTED'].includes(msg.event)) {
        refreshData();
      }
    }, setWsStatus);

    return () => {
      try { ws.close(); } catch {}
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    };
  }, [refreshData]);

  // ── Derived KPIs ──────────────────────────────────────────────────────────
  const kpi = useMemo(() => {
    const total = liveRobots.length || 4;
    const faults = liveRobots.filter((r) => r.status === 'DEAD' || r.status === 'FAULT' || r.status === 'FAILED').length;
    const active = liveRobots.filter((r) =>
      ['ACTIVE', 'MOVING', 'DISPATCHING', 'TRANSPORTING', 'LOADING'].includes((r.status || '').toUpperCase())
    ).length;
    const available = Math.max(0, total - active - faults);
    const completed = (snapshot?.metrics?.completed_tasks ?? 0) + (activeTask?.status === 'COMPLETED' ? 1 : 0);
    const activeTasks = (snapshot?.tasks?.filter((t) => t.status !== 'COMPLETED')?.length ?? 0) || (activeTask && activeTask.status !== 'COMPLETED' ? 1 : 0);
    const routeDistanceM = activeRoute.length > 1 ? (activeRoute.length - 1) * 2.2 : 0;

    return {
      total,
      active,
      available,
      faults,
      completed,
      activeTasks,
      racks: 78,
      rfNodes: 98,
      routeDistanceM,
    };
  }, [liveRobots, snapshot, activeRoute, activeTask]);

  const systemOnline = snapshot?.health?.status === 'ok';

  // Latest active allocation
  const currentAllocation = snapshot?.allocations?.find((a) => a.task_id === activeTask?.task_id) || snapshot?.allocations?.[0];

  // ── Task Creation & Decentralized Allocation Execution ────────────────────
  async function handleCreateTask(e?: React.FormEvent) {
    if (e) e.preventDefault();
    const taskId = taskForm.task_id.trim() || `TASK_${Date.now().toString().slice(-4)}`;
    const pickup = taskForm.pickup_node;
    const dest = taskForm.dispatch_node;

    if (!pickup || !dest) {
      setActionMsg('Please specify both Pickup and Destination RF nodes.');
      return;
    }
    if (pickup === dest) {
      setActionMsg('Pickup and Destination cannot be the same RF node.');
      return;
    }

    setIsDispatching(true);
    setProgressPercent(0);
    setActionMsg(`Announcing ${taskId} to AMR edge agents (Pickup: ${pickup} → Dest: ${dest})…`);

    try {
      const payload: Partial<BackendTask> = {
        task_id: taskId,
        pickup_node: pickup,
        dispatch_node: dest,
        priority: taskForm.priority,
        deadline: Number(taskForm.deadline) || 120,
        load: 1.0,
        energy_requirement: 10.0,
      };

      const res = await postTask(payload);
      const winnerId = res.winner;
      const plannedPath = res.path && res.path.length > 0 ? res.path : [];

      setActiveRoute(plannedPath);
      setActiveTask({
        task_id: taskId,
        pickup_node: pickup,
        dispatch_node: dest,
        winner: winnerId,
        status: winnerId ? 'IN_PROGRESS' : 'PENDING',
        priority: taskForm.priority,
      });

      if (winnerId) {
        setActionMsg(`✓ Decentralized CBAA Winner: ${winnerId}! Executing ${plannedPath.length}-hop route on RF graph…`);
      } else {
        setActionMsg(`Task ${taskId} registered in queue.`);
      }

      // Smooth frontend transit simulation
      if (plannedPath.length > 1 && winnerId) {
        let currentStep = 0;
        if (stepTimerRef.current) clearInterval(stepTimerRef.current);

        stepTimerRef.current = setInterval(() => {
          currentStep++;
          const pct = Math.min(100, Math.round((currentStep / Math.max(1, plannedPath.length - 1)) * 100));
          setProgressPercent(pct);

          if (currentStep < plannedPath.length) {
            const currentNode = plannedPath[currentStep];
            const isAtPickup = currentNode === pickup;
            const status = isAtPickup ? 'LOADING' : currentStep < plannedPath.indexOf(pickup) ? 'DISPATCHING' : 'TRANSPORTING';

            setLiveRobots((prev) =>
              prev.map((r) =>
                r.robot_id === winnerId
                  ? {
                      ...r,
                      node_id: currentNode,
                      status: status,
                      battery: Math.max(10, r.battery - 0.2),
                    }
                  : r
              )
            );
          } else {
            clearInterval(stepTimerRef.current);
            setLiveRobots((prev) =>
              prev.map((r) =>
                r.robot_id === winnerId
                  ? {
                      ...r,
                      node_id: plannedPath[plannedPath.length - 1],
                      status: 'AVAILABLE',
                      battery: Math.max(10, r.battery - 0.2),
                    }
                  : r
              )
            );
            setActiveTask((prev: any) => ({ ...prev, status: 'COMPLETED' }));
            setProgressPercent(100);
            setIsDispatching(false);
            setActionMsg(`🎉 Mission ${taskId} completed by ${winnerId}! Delivered to ${dest}.`);
            refreshData();
          }
        }, 550);
      } else {
        setIsDispatching(false);
      }

      await refreshData();
    } catch (err) {
      setIsDispatching(false);
      setActionMsg(`Task creation error: ${String(err)}`);
    }
  }

  // ── Node Click from Map ───────────────────────────────────────────────────
  function handleNodeClick(nodeId: string) {
    if (taskForm.pickup_node === nodeId) {
      setActionMsg(`Node ${nodeId} already selected as Pickup.`);
      return;
    }
    setTaskForm((prev) => ({ ...prev, dispatch_node: nodeId }));
    setActionMsg(`Set destination to ${nodeId}. Click "CREATE TASK" to compute bids and dispatch.`);
  }

  // ── Simulation Dynamic Obstacle & Fault Handlers ──────────────────────────
  async function handleAddObstacle() {
    try {
      setActionMsg(`Adding dynamic obstacle at (${obstacleX}, ${obstacleY})…`);
      await postSimObstacle(obstacleX, obstacleY, `OBS_${Date.now().toString().slice(-4)}`);
      setActionMsg(`✓ Obstacle placed at (${obstacleX}, ${obstacleY}). AMRs will detect it via LiDAR!`);
    } catch (err) {
      setActionMsg(`Failed to add obstacle: ${String(err)}`);
    }
  }

  async function handleFailRobot() {
    try {
      setActionMsg(`Injecting fault into AMR ${failTarget}…`);
      await postSimFailRobot(failTarget);
      setActionMsg(`❌ AMR ${failTarget} stopped/faulted. CBAA failover will reallocate active missions.`);
    } catch (err) {
      setActionMsg(`Fail robot error: ${String(err)}`);
    }
  }

  async function handleRecoverRobot() {
    try {
      setActionMsg(`Recovering AMR ${failTarget}…`);
      await postSimRecoverRobot(failTarget);
      setActionMsg(`✓ AMR ${failTarget} restored to healthy AVAILABLE standby.`);
    } catch (err) {
      setActionMsg(`Recover robot error: ${String(err)}`);
    }
  }

  // ── Batch Task Upload ─────────────────────────────────────────────────────
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    if (file.name.endsWith('.json')) {
      reader.onload = (ev) => {
        try {
          const raw = JSON.parse(ev.target?.result as string);
          setDatasetPreview(Array.isArray(raw) ? raw : [raw]);
          setActionMsg(`Loaded ${Array.isArray(raw) ? raw.length : 1} tasks from ${file.name}`);
        } catch (err) { setActionMsg('Parse error: ' + err); }
      };
      reader.readAsText(file);
    } else {
      reader.onload = (ev) => {
        try {
          const wb = XLSX.read(ev.target?.result, { type: 'binary' });
          const rows = XLSX.utils.sheet_to_json<any>(wb.Sheets[wb.SheetNames[0]]);
          setDatasetPreview(rows);
          setActionMsg(`Loaded ${rows.length} rows from ${file.name}`);
        } catch (err) { setActionMsg('Parse error: ' + err); }
      };
      reader.readAsBinaryString(file);
    }
  }

  async function handleImportTasks() {
    if (!datasetPreview.length) return;
    try {
      await postBatchTasks(datasetPreview);
      setActionMsg(`Imported ${datasetPreview.length} tasks.`);
      setDatasetPreview([]);
      await refreshData();
    } catch (err) { setActionMsg(String(err)); }
  }

  // ── Loading Screen ────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="loading-screen">
        <div className="loading-spinner" />
        <div className="brand">SWARM-X PRO V2</div>
        <div className="sub">Initializing Real 78-Rack Decentralized Warehouse Fleet…</div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* ── HEADER ── */}
      <Header
        systemOnline={systemOnline}
        wsStatus={wsStatus}
        meshCount={liveRobots.filter((r) => r.status !== 'DEAD' && r.status !== 'FAULT' && r.status !== 'FAILED').length}
        meshTotal={liveRobots.length || 4}
        simRunning={isDispatching}
        onSync={refreshData}
      />

      {/* ── ACTION NOTIFICATION BANNER ── */}
      {actionMsg && (
        <div className="action-notification-bar">
          <span className="notif-icon">ℹ</span>
          <span className="notif-text">{actionMsg}</span>
          <button className="notif-close" onClick={() => setActionMsg('')}>×</button>
        </div>
      )}

      {/* ── ERROR BANNER ── */}
      {backendError && (
        <div className="error-banner">
          <span>⚠ {backendError}</span>
          <button className="btn btn-sm" onClick={refreshData}>Retry</button>
        </div>
      )}

      {/* ── MAIN NAVIGATION TABS ── */}
      <nav className="tab-nav">
        {NAV_TABS.map((t) => (
          <button
            key={t}
            className={`tab-btn ${tab === t ? 'active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
        <div className="tab-spacer" />
        <div className="tab-meta">
          <span className="mono" style={{ fontSize: 13 }}>
            WAREHOUSE: <strong>78 RACKS</strong> · <strong>98 RF NODES</strong> · <strong>4 AMRs</strong>
          </span>
        </div>
      </nav>

      {/* ── KPI METRICS BAR ── */}
      <KpiBar
        racks={kpi.racks}
        rfNodes={kpi.rfNodes}
        totalRobots={kpi.total}
        activeRobots={kpi.active}
        availableRobots={kpi.available}
        faultRobots={kpi.faults}
        activeTasks={kpi.activeTasks}
        completedTasks={kpi.completed}
        routeDistanceM={kpi.routeDistanceM}
      />

      {/* ── PAGE CONTENT CONTAINER ── */}
      <div className="main-content">

        {/* ── OVERVIEW TAB ── */}
        {tab === 'Overview' && (
          <div className="page-layout">
            {/* Quick Task Creation & Dispatch Form Bar */}
            <div className="quick-dispatch-bar">
              <div className="dispatch-header">
                <span className="dispatch-title">OPERATIONAL TASK INJECTION &amp; FLEET DISPATCH</span>
                <span className="dispatch-desc">
                  Enter pickup &amp; destination nodes to initiate peer-to-peer CBAA bidding among the 4 AMR edge agents.
                </span>
              </div>

              <div className="dispatch-form-row">
                <div className="node-selector-wrap">
                  <span className="node-selector-label">Task ID:</span>
                  <input
                    type="text"
                    className="node-input-select"
                    style={{ width: 120, padding: '6px 8px' }}
                    value={taskForm.task_id}
                    placeholder="Auto-gen"
                    onChange={(e) => setTaskForm((p) => ({ ...p, task_id: e.target.value }))}
                    disabled={isDispatching}
                  />
                </div>

                <div className="node-selector-wrap">
                  <span className="node-selector-label">Pickup RF Node:</span>
                  <select
                    className="node-input-select"
                    value={taskForm.pickup_node}
                    onChange={(e) => setTaskForm((p) => ({ ...p, pickup_node: e.target.value }))}
                    disabled={isDispatching}
                  >
                    {ALL_RF_NODES.map((n) => (
                      <option key={`p_${n}`} value={n}>{n}</option>
                    ))}
                  </select>
                </div>

                <div className="node-selector-wrap">
                  <span className="node-selector-label">Destination RF Node:</span>
                  <select
                    className="node-input-select"
                    value={taskForm.dispatch_node}
                    onChange={(e) => setTaskForm((p) => ({ ...p, dispatch_node: e.target.value }))}
                    disabled={isDispatching}
                  >
                    {ALL_RF_NODES.map((n) => (
                      <option key={`d_${n}`} value={n}>{n}</option>
                    ))}
                  </select>
                </div>

                <div className="node-selector-wrap">
                  <span className="node-selector-label">Priority:</span>
                  <select
                    className="node-input-select"
                    style={{ minWidth: 100 }}
                    value={taskForm.priority}
                    onChange={(e) => setTaskForm((p) => ({ ...p, priority: e.target.value }))}
                    disabled={isDispatching}
                  >
                    <option value="NORMAL">NORMAL</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>

                <button
                  className="btn-dispatch"
                  onClick={() => handleCreateTask()}
                  disabled={isDispatching}
                >
                  {isDispatching ? '⏳ NAVIGATING ROUTE…' : '⚡ CREATE & DISPATCH TASK'}
                </button>
              </div>

              {/* Waypoint Hint */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 13, color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: 10 }}>
                <span>
                  💡 <strong>Tip:</strong> You can also <strong>click any RF node on the map</strong> below to set it as the destination!
                </span>
                <span className="mono" style={{ fontWeight: 700, color: 'var(--accent)' }}>
                  Active AMR: {activeTask?.winner || '—'} · Mission: {activeTask?.task_id || 'IDLE'}
                </span>
              </div>
            </div>

            {/* Simulation Quick Control Strip */}
            <div className="quick-dispatch-bar" style={{ marginTop: 10, background: 'var(--bg-surface-elevated, #161b22)', display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--accent, #38bdf8)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  SIMULATION CONTROLS:
                </span>
                {/* Obstacle controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Aisle (X, Y):</span>
                  <input
                    type="number"
                    step="0.5"
                    className="node-input-select"
                    style={{ width: 70, padding: '4px 8px' }}
                    value={obstacleX}
                    onChange={(e) => setObstacleX(parseFloat(e.target.value) || 0)}
                    title="Obstacle X coordinate"
                  />
                  <input
                    type="number"
                    step="0.5"
                    className="node-input-select"
                    style={{ width: 70, padding: '4px 8px' }}
                    value={obstacleY}
                    onChange={(e) => setObstacleY(parseFloat(e.target.value) || 0)}
                    title="Obstacle Y coordinate"
                  />
                  <button className="btn btn-sm btn-warning" onClick={handleAddObstacle}>
                    + ADD OBSTACLE
                  </button>
                </div>

                {/* Robot failure controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginLeft: 10, borderLeft: '1px solid var(--border-subtle)', paddingLeft: 10 }}>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>AMR:</span>
                  <select
                    className="node-input-select"
                    style={{ width: 80, padding: '4px 8px' }}
                    value={failTarget}
                    onChange={(e) => setFailTarget(e.target.value)}
                  >
                    <option value="R1">R1</option>
                    <option value="R2">R2</option>
                    <option value="R3">R3</option>
                    <option value="R4">R4</option>
                  </select>
                  <button className="btn btn-sm btn-danger" onClick={handleFailRobot}>
                    FAIL ROBOT
                  </button>
                  <button className="btn btn-sm" onClick={handleRecoverRobot}>
                    RECOVER
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-sm" onClick={() => setTab('3D Simulation')}>
                  VIEW 3D SIMULATION ↗
                </button>
                <button className="btn btn-sm" onClick={() => setTab('SLAM')}>
                  VIEW SLAM MONITOR ↗
                </button>
              </div>
            </div>

            {/* MAIN TWO-COLUMN SPLIT */}
            <div className="overview-grid">
              {/* LEFT COLUMN: 2D Digital Twin Map & CBAA Panel */}
              <div className="overview-left">
                {/* 2D Digital Twin Map */}
                <div className="map-panel">
                  <div className="panel-header">
                    <span className="panel-title">
                      Warehouse RF Navigation Digital Twin
                    </span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                      78 RACKS · 98 RF AISLE NODES · 4 CORNER AMRs
                    </span>
                  </div>
                  <WarehouseMap
                    robots={liveRobots}
                    warehouseData={warehouseData}
                    activeRoute={activeRoute}
                    activeTask={activeTask}
                    onRobotClick={(rid) => setActionMsg(`AMR ${rid} telemetry: ${liveRobots.find((r) => r.robot_id === rid)?.status}, at ${liveRobots.find((r) => r.robot_id === rid)?.node_id}`)}
                    onNodeClick={handleNodeClick}
                  />
                </div>

                {/* CBAA Consensus Transparency Panel */}
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title panel-title-accent">
                      CBAA Consensus Auction Transparency
                    </span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 700 }}>
                      {activeTask?.task_id ? `TASK: ${activeTask.task_id}` : 'STANDBY'}
                    </span>
                  </div>
                  <CbaaPanel
                    allocation={currentAllocation}
                    config={snapshot?.config}
                    robots={liveRobots}
                  />
                </div>
              </div>

              {/* RIGHT COLUMN: Mission Card, Fleet Status, and Progression */}
              <div className="overview-right">
                {/* Active Mission Card */}
                <MissionCard
                  allocation={currentAllocation}
                  activeTask={activeTask}
                  activeRoute={activeRoute}
                  robotStatus={liveRobots.find((r) => r.robot_id === activeTask?.winner)?.status || 'AVAILABLE'}
                  progressPercent={progressPercent}
                />

                {/* Fleet Table */}
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title">AMR Fleet Status</span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 700 }}>
                      {kpi.faults > 0 && <span style={{ color: 'var(--fault)', fontWeight: 800 }}>● {kpi.faults} FAULT  </span>}
                      {kpi.active} ACTIVE · {kpi.available} AVAILABLE
                    </span>
                  </div>
                  <FleetTable
                    robots={liveRobots}
                    allocations={snapshot?.allocations ?? []}
                    paths={snapshot?.paths ?? []}
                  />
                </div>

                {/* SLAM Odometry Panel */}
                <div className="panel">
                  <div className="panel-header">
                    <span className="panel-title panel-title-accent">
                      SLAM &amp; Odometry Validation
                    </span>
                    <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                      {activeRoute.length > 0 ? `${activeRoute.length} Waypoint Poses` : 'Standby'}
                    </span>
                  </div>
                  <SlamPanel
                    slamScans={activeRoute.length}
                    routeDistanceM={kpi.routeDistanceM}
                    travelTimeS={activeRoute.length > 1 ? (activeRoute.length - 1) * 2.2 : 0}
                    status={isDispatching ? 'TRACKING' : 'IDLE'}
                    activeRoute={activeRoute}
                  />
                </div>
              </div>
            </div>

            {/* BOTTOM: LIVE EVENT FEED */}
            <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-header">
                <span className="panel-title">Live System Event Feed</span>
                <span className="mono" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {eventLog.length} events logged · Real-time simulation telemetry &amp; node arbitration
                </span>
              </div>
              <EventFeed eventLog={eventLog} />
            </div>
          </div>
        )}

        {/* ── DEMO MODE PAGE (Section 29) ── */}
        {tab === 'Demo' && (
          <div className="page-layout">
            <DemoView
              robots={liveRobots}
              activeRoute={activeRoute}
              activeTask={activeTask}
              liveTelemetry={liveTelemetry}
              eventLog={eventLog}
              onDispatchDemoTasks={refreshData}
            />
          </div>
        )}

        {/* ── TASKS PAGE (OPERATOR INJECTION & ACTIVE TASKS) ── */}
        {tab === 'Tasks' && (
          <div className="page-layout" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Task File Ingestion & Strict Validation (CSV / JSON) */}
            <TaskImportPanel onTasksDispatched={refreshData} />

            {/* Operator Task Injection Card */}
            <div className="panel" style={{ padding: '18px 20px' }}>
              <div className="panel-header" style={{ padding: '0 0 14px', borderBottom: '1.5px solid var(--border-subtle)', marginBottom: 14 }}>
                <span className="panel-title">Operator Task Dispatch Center</span>
                <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  Inject tasks directly to AMR edge agents for decentralized auction and execution
                </span>
              </div>

              <form onSubmit={handleCreateTask}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 14, marginBottom: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Task ID
                    </label>
                    <input
                      type="text"
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.task_id}
                      placeholder="e.g. TASK_PICK_01"
                      onChange={(e) => setTaskForm((p) => ({ ...p, task_id: e.target.value }))}
                      disabled={isDispatching}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Pickup RF Node
                    </label>
                    <select
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.pickup_node}
                      onChange={(e) => setTaskForm((p) => ({ ...p, pickup_node: e.target.value }))}
                      disabled={isDispatching}
                    >
                      {ALL_RF_NODES.map((n) => (
                        <option key={`tp_${n}`} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Destination RF Node
                    </label>
                    <select
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.dispatch_node}
                      onChange={(e) => setTaskForm((p) => ({ ...p, dispatch_node: e.target.value }))}
                      disabled={isDispatching}
                    >
                      {ALL_RF_NODES.map((n) => (
                        <option key={`td_${n}`} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Priority
                    </label>
                    <select
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.priority}
                      onChange={(e) => setTaskForm((p) => ({ ...p, priority: e.target.value }))}
                      disabled={isDispatching}
                    >
                      <option value="NORMAL">NORMAL</option>
                      <option value="HIGH">HIGH</option>
                      <option value="CRITICAL">CRITICAL</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Task Type
                    </label>
                    <select
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.task_type}
                      onChange={(e) => setTaskForm((p) => ({ ...p, task_type: e.target.value }))}
                      disabled={isDispatching}
                    >
                      <option value="TRANSPORT">TRANSPORT</option>
                      <option value="PICKUP">PICKUP</option>
                      <option value="DELIVERY">DELIVERY</option>
                      <option value="TRANSFER">TRANSFER</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 700, marginBottom: 6, color: 'var(--text-secondary)' }}>
                      Deadline (s)
                    </label>
                    <input
                      type="number"
                      className="node-input-select"
                      style={{ width: '100%', padding: '8px 10px' }}
                      value={taskForm.deadline}
                      min={10}
                      max={3600}
                      onChange={(e) => setTaskForm((p) => ({ ...p, deadline: e.target.value }))}
                      disabled={isDispatching}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                  <button
                    className="btn btn-primary"
                    type="submit"
                    disabled={isDispatching}
                    style={{ padding: '10px 24px', fontSize: 14, fontWeight: 800 }}
                  >
                    {isDispatching ? 'DISPATCHING…' : 'CREATE TASK'}
                  </button>
                </div>
              </form>
            </div>

            {/* Active & Registered Tasks Table */}
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Active &amp; Registered Tasks</span>
                <span className="mono" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {snapshot?.tasks?.length ?? 0} registered tasks
                </span>
              </div>
              <div className="full-table-container">
                {(!snapshot?.tasks || snapshot.tasks.length === 0) && !activeTask ? (
                  <div style={{ padding: '36px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
                      NO ACTIVE TASKS
                    </div>
                    <div style={{ fontSize: 13 }}>
                      No tasks are currently registered or in queue. Use the form above to create a real decentralized task.
                    </div>
                  </div>
                ) : (
                  <table className="full-table">
                    <thead>
                      <tr>
                        <th>Task ID</th>
                        <th>Pickup RF Node</th>
                        <th>Target Destination</th>
                        <th>Priority</th>
                        <th>Deadline</th>
                        <th>Assigned AMR</th>
                        <th>Status</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(snapshot?.tasks || (activeTask ? [activeTask] : [])).map((t) => {
                        const alloc = snapshot?.allocations?.find((a) => a.task_id === t.task_id);
                        const isCurrent = activeTask?.task_id === t.task_id;
                        const winner = alloc?.winner || (isCurrent ? activeTask.winner : null);

                        return (
                          <tr key={t.task_id}>
                            <td>
                              <span className="mono" style={{ fontWeight: 800, fontSize: 14 }}>
                                {t.task_id}
                              </span>
                            </td>
                            <td><span className="mono" style={{ fontWeight: 700 }}>{t.pickup_node}</span></td>
                            <td><span className="mono" style={{ fontWeight: 700 }}>{t.dispatch_node}</span></td>
                            <td>
                              <span className={`badge ${t.priority === 'CRITICAL' ? 'badge-fault' : t.priority === 'HIGH' ? 'badge-warning' : 'badge-neutral'}`}>
                                {t.priority}
                              </span>
                            </td>
                            <td className="mono">{t.deadline ? `${t.deadline}s` : '—'}</td>
                            <td>
                              {winner ? (
                                <span className="badge badge-success">{winner}</span>
                              ) : (
                                <span className="badge badge-neutral">—</span>
                              )}
                            </td>
                            <td>
                              <span className={`badge ${isCurrent && isDispatching ? 'badge-warning' : winner ? 'badge-success' : 'badge-neutral'}`}>
                                {isCurrent && isDispatching ? 'DISPATCHING' : winner ? 'ALLOCATED' : 'PENDING'}
                              </span>
                            </td>
                            <td>
                              <button
                                className="btn btn-sm btn-primary"
                                onClick={() => {
                                  setTab('Overview');
                                  setTaskForm((p) => ({
                                    ...p,
                                    pickup_node: t.pickup_node,
                                    dispatch_node: t.dispatch_node,
                                    priority: t.priority,
                                  }));
                                  handleCreateTask();
                                }}
                                disabled={isDispatching}
                              >
                                Re-Dispatch
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── 3D SIMULATION (PYBULLET 3D WAREHOUSE) ── */}
        {tab === '3D Simulation' && (
          <div className="page-layout">
            <Warehouse3DView
              robots={liveRobots}
              activeRoute={activeRoute}
              activeTask={activeTask}
              liveTelemetry={liveTelemetry}
            />
          </div>
        )}

        {/* ── SLAM (REALTIME 2D OCCUPANCY GRID) ── */}
        {tab === 'SLAM' && (
          <div className="page-layout">
            <SlamView liveSlamData={liveSlamData} />
          </div>
        )}

        {/* ── MAP (FULLSCREEN CAD VIEW) ── */}
        {tab === 'Map' && (
          <div style={{ height: 'calc(100vh - var(--header-h) - var(--nav-h) - var(--kpi-h) - 40px)', display: 'flex', flexDirection: 'column' }}>
            <div style={{ padding: '12px 18px', background: 'var(--bg-surface)', borderBottom: '1.5px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: 15, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--text-primary)' }}>
                Warehouse RF Navigation Grid — High Precision CAD View
              </span>
              <span className="mono" style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 700 }}>
                78 RACKS · 98 RF AISLE NODES · 4 CORNER AMRs ({liveRobots.map(r => `${r.robot_id}@${r.node_id}`).join(' · ')})
              </span>
            </div>
            <div style={{ flex: 1, minHeight: 0 }}>
              <WarehouseMap
                robots={liveRobots}
                warehouseData={warehouseData}
                activeRoute={activeRoute}
                activeTask={activeTask}
                onNodeClick={handleNodeClick}
              />
            </div>
          </div>
        )}

        {/* ── FLEET DETAILS ── */}
        {tab === 'Fleet' && (
          <div className="page-layout">
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">AMR Autonomous Fleet — Telemetry Overview</span>
                <span className="mono" style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                  {kpi.total} units · {kpi.faults} faults · {kpi.available} available
                </span>
              </div>
              <FleetTable
                robots={liveRobots}
                allocations={snapshot?.allocations ?? []}
                paths={snapshot?.paths ?? []}
              />
            </div>
          </div>
        )}

        {/* ── PERFORMANCE BENCHMARK (Section 26-28) ── */}
        {tab === 'Performance' && (
          <div className="page-layout">
            <PerformanceView />
          </div>
        )}

        {/* ── EVENTS STREAM ── */}
        {tab === 'Events' && (
          <div className="page-layout">
            <div className="panel">
              <div className="panel-header">
                <span className="panel-title">Live System Event Stream</span>
                <span className="mono" style={{ fontSize: 13, color: 'var(--text-muted)' }}>{eventLog.length} events logged</span>
              </div>
              <EventFeed eventLog={eventLog} />
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
