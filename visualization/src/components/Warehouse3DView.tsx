import React, { useEffect, useRef, useState, useCallback } from 'react';
import type { BackendRobot } from '../types/backend';
import {
  fetchSimulationStatus,
  postSimStart,
  postSimStop,
  postSimReset,
  postSimObstacle,
  postSimFailRobot,
  postSimRecoverRobot,
} from '../services/api';

interface Props {
  robots: BackendRobot[];
  activeRoute?: string[];
  activeTask?: any;
  liveTelemetry?: any;
}

// 78 Racks (13 cols x 6 rows) matching backend/data/warehouse_real.py
const GRID_COLS = 13;
const GRID_ROWS = 6;
const SPACING_X = 2.4;
const SPACING_Y = 2.0;
const X_MIN = -15.6;
const X_MAX = 15.6;
const Y_MIN = -6.0;
const Y_MAX = 6.0;
const RACK_W = 1.4;
const RACK_H = 0.8;

interface Rack3D {
  id: string;
  x: number;
  y: number;
}

const RACKS_3D: Rack3D[] = [];
let rackIdx = 1;
for (let r = 0; r < GRID_ROWS; r++) {
  const yc = Number((Y_MIN + r * SPACING_Y + SPACING_Y / 2.0).toFixed(2));
  for (let c = 0; c < GRID_COLS; c++) {
    const xc = Number((X_MIN + c * SPACING_X + SPACING_X / 2.0).toFixed(2));
    RACKS_3D.push({
      id: `RACK_${String(rackIdx).padStart(2, '0')}`,
      x: xc,
      y: yc,
    });
    rackIdx++;
  }
}

// 98 RF Nodes (14 cols x 7 rows)
interface RFNode3D {
  id: string;
  x: number;
  y: number;
}

const RF_NODES_3D: RFNode3D[] = [];
for (let r = 0; r <= GRID_ROWS; r++) {
  const yn = Number((Y_MIN + r * SPACING_Y).toFixed(2));
  for (let c = 0; c <= GRID_COLS; c++) {
    const xn = Number((X_MIN + c * SPACING_X).toFixed(2));
    RF_NODES_3D.push({
      id: `RF_${r}_{c}`,
      x: xn,
      y: yn,
    });
  }
}

export function Warehouse3DView({
  robots,
  activeRoute = [],
  activeTask,
  liveTelemetry,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [simStatus, setSimStatus] = useState<any>(null);
  const [targetRobotToFail, setTargetRobotToFail] = useState<string>('R1');
  const [obstacleNode, setObstacleNode] = useState<string>('RF_3_5');
  const [actionNotice, setActionNotice] = useState<string>('');

  // 3D Camera State
  const [camRotX, setCamRotX] = useState<number>(55); // Pitch (degrees)
  const [camRotZ, setCamRotZ] = useState<number>(-40); // Yaw (degrees)
  const [camZoom, setCamZoom] = useState<number>(24);
  const [camPanX, setCamPanX] = useState<number>(0);
  const [camPanY, setCamPanY] = useState<number>(0);
  const isDragging = useRef<boolean>(false);
  const lastMousePos = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Dynamic Obstacles list
  const [obstacles, setObstacles] = useState<Array<{ id: string; x: number; y: number }>>([]);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetchSimulationStatus();
      if (res) setSimStatus(res);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 2000);
    return () => clearInterval(interval);
  }, [loadStatus]);

  // Sync robots telemetry from PyBullet
  const effectiveRobots = React.useMemo(() => {
    if (liveTelemetry && liveTelemetry.robots && liveTelemetry.robots.length >= 4) {
      return liveTelemetry.robots;
    }
    return robots;
  }, [liveTelemetry, robots]);

  // Mouse Orbit / Zoom controls
  const handleMouseDown = (e: React.MouseEvent) => {
    isDragging.current = true;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;
    lastMousePos.current = { x: e.clientX, y: e.clientY };

    if (e.buttons === 1) {
      // Left drag: Orbit
      setCamRotZ((prev) => prev + dx * 0.4);
      setCamRotX((prev) => Math.max(15, Math.min(85, prev + dy * 0.3)));
    } else if (e.buttons === 2) {
      // Right drag: Pan
      setCamPanX((prev) => prev + dx * 0.05);
      setCamPanY((prev) => prev - dy * 0.05);
    }
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setCamZoom((prev) => Math.max(12, Math.min(50, prev + e.deltaY * 0.03)));
  };

  // 3D Rendering Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const cw = canvas.width;
    const ch = canvas.height;

    // Projection transforms
    const radX = (camRotX * Math.PI) / 180;
    const radZ = (camRotZ * Math.PI) / 180;
    const cosX = Math.cos(radX);
    const sinX = Math.sin(radX);
    const cosZ = Math.cos(radZ);
    const sinZ = Math.sin(radZ);

    const project = (wx: number, wy: number, wz: number) => {
      // World to Camera frame
      const x0 = wx + camPanX;
      const y0 = wy + camPanY;
      const z0 = wz;

      // Rotate around Z (Yaw)
      const x1 = x0 * cosZ - y0 * sinZ;
      const y1 = x0 * sinZ + y0 * cosZ;
      const z1 = z0;

      // Rotate around X (Pitch)
      const x2 = x1;
      const y2 = y1 * cosX - z1 * sinX;
      const z2 = y1 * sinX + z1 * cosX;

      // Perspective projection
      const scale = (cw / 1.6) / (camZoom + y2 * 0.45);
      const px = cw / 2 + x2 * scale;
      const py = ch / 2 - z2 * scale;
      return { px, py, depth: y2 };
    };

    // 1. Clear background (Industrial dark room)
    ctx.fillStyle = '#080C14';
    ctx.fillRect(0, 0, cw, ch);

    // 2. Draw Floor Slab
    const floorCorners = [
      project(-18.0, -8.0, 0.0),
      project(18.0, -8.0, 0.0),
      project(18.0, 8.0, 0.0),
      project(-18.0, 8.0, 0.0),
    ];
    ctx.beginPath();
    ctx.moveTo(floorCorners[0].px, floorCorners[0].py);
    for (let i = 1; i < 4; i++) ctx.lineTo(floorCorners[i].px, floorCorners[i].py);
    ctx.closePath();
    ctx.fillStyle = '#111827';
    ctx.fill();
    ctx.strokeStyle = '#1F2937';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // 3. Draw Orthogonal Aisle Grid Lines
    ctx.strokeStyle = 'rgba(51, 65, 85, 0.4)';
    ctx.lineWidth = 1.0;
    // Horizontal lines
    for (let r = 0; r <= GRID_ROWS; r++) {
      const y = Y_MIN + r * SPACING_Y;
      const p1 = project(X_MIN, y, 0.01);
      const p2 = project(X_MAX, y, 0.01);
      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.stroke();
    }
    // Vertical lines
    for (let c = 0; c <= GRID_COLS; c++) {
      const x = X_MIN + c * SPACING_X;
      const p1 = project(x, Y_MIN, 0.01);
      const p2 = project(x, Y_MAX, 0.01);
      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.stroke();
    }

    // 4. Draw 98 RF Intersection Nodes
    for (const node of RF_NODES_3D) {
      const p = project(node.x, node.y, 0.02);
      ctx.beginPath();
      ctx.arc(p.px, p.py, 2.0, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(56, 189, 248, 0.4)';
      ctx.fill();
    }

    // 5. Draw Active Route Waypoints Path
    if (activeRoute && activeRoute.length > 1) {
      ctx.beginPath();
      const nodeMap: Record<string, { x: number; y: number }> = {};
      for (const n of RF_NODES_3D) nodeMap[n.id] = { x: n.x, y: n.y };

      const pFirst = nodeMap[activeRoute[0]];
      if (pFirst) {
        const pr = project(pFirst.x, pFirst.y, 0.08);
        ctx.moveTo(pr.px, pr.py);
        for (let i = 1; i < activeRoute.length; i++) {
          const pt = nodeMap[activeRoute[i]];
          if (pt) {
            const nextPr = project(pt.x, pt.y, 0.08);
            ctx.lineTo(nextPr.px, nextPr.py);
          }
        }
        ctx.strokeStyle = '#38BDF8';
        ctx.lineWidth = 3.5;
        ctx.stroke();
      }
    }

    // 6. Draw 78 Industrial 3D Racks (Depth Sorted)
    // Sort racks by camera depth for correct painter's algorithm rendering
    const sortedRacks = [...RACKS_3D].sort((a, b) => {
      const da = a.x * sinZ + a.y * cosZ;
      const db = b.x * sinZ + b.y * cosZ;
      return db - da;
    });

    const rackHeight = 1.8;
    for (const rack of sortedRacks) {
      const x = rack.x;
      const y = rack.y;
      const hw = RACK_W / 2.0;
      const hh = RACK_H / 2.0;

      // Bottom shelf
      const b0 = project(x - hw, y - hh, 0.15);
      const b1 = project(x + hw, y - hh, 0.15);
      const b2 = project(x + hw, y + hh, 0.15);
      const b3 = project(x - hw, y + hh, 0.15);

      // Top shelf
      const t0 = project(x - hw, y - hh, rackHeight);
      const t1 = project(x + hw, y - hh, rackHeight);
      const t2 = project(x + hw, y + hh, rackHeight);
      const t3 = project(x - hw, y + hh, rackHeight);

      // Mid shelf
      const m0 = project(x - hw, y - hh, 0.95);
      const m1 = project(x + hw, y - hh, 0.95);
      const m2 = project(x + hw, y + hh, 0.95);
      const m3 = project(x - hw, y + hh, 0.95);

      // Draw 4 Upright Steel Posts (Industrial Blue)
      ctx.strokeStyle = '#1D4ED8';
      ctx.lineWidth = 2.0;
      ctx.beginPath();
      ctx.moveTo(b0.px, b0.py);
      ctx.lineTo(t0.px, t0.py);
      ctx.moveTo(b1.px, b1.py);
      ctx.lineTo(t1.px, t1.py);
      ctx.moveTo(b2.px, b2.py);
      ctx.lineTo(t2.px, t2.py);
      ctx.moveTo(b3.px, b3.py);
      ctx.lineTo(t3.px, t3.py);
      ctx.stroke();

      // Draw Top Shelf Deck (Safety Orange)
      ctx.beginPath();
      ctx.moveTo(t0.px, t0.py);
      ctx.lineTo(t1.px, t1.py);
      ctx.lineTo(t2.px, t2.py);
      ctx.lineTo(t3.px, t3.py);
      ctx.closePath();
      ctx.fillStyle = '#EA580C';
      ctx.fill();
      ctx.strokeStyle = '#C2410C';
      ctx.lineWidth = 1.0;
      ctx.stroke();

      // Draw Mid Shelf Deck
      ctx.beginPath();
      ctx.moveTo(m0.px, m0.py);
      ctx.lineTo(m1.px, m1.py);
      ctx.lineTo(m2.px, m2.py);
      ctx.lineTo(m3.px, m3.py);
      ctx.closePath();
      ctx.fillStyle = '#F97316';
      ctx.fill();

      // Cargo packages on middle shelf
      const cp1 = project(x - 0.25, y, 1.25);
      ctx.fillStyle = '#B45309';
      ctx.fillRect(cp1.px - 6, cp1.py - 6, 12, 12);
    }

    // 7. Draw Dynamic Obstacles
    for (const obs of obstacles) {
      const p = project(obs.x, obs.y, 0.4);
      ctx.fillStyle = '#EAB308';
      ctx.beginPath();
      ctx.arc(p.px, p.py, 10, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#000000';
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = '#000000';
      ctx.font = 'bold 9px monospace';
      ctx.fillText('HAZARD', p.px - 16, p.py + 3);
    }

    // 8. Draw 4 AMRs
    const robotPalette: Record<string, string> = {
      R1: '#0284C7', // Blue
      R2: '#EA580C', // Amber
      R3: '#16A34A', // Green
      R4: '#9333EA', // Purple
    };

    for (const r of effectiveRobots) {
      const rx = typeof r.x === 'number' ? r.x : (r.position ? r.position[0] : 0);
      const ry = typeof r.y === 'number' ? r.y : (r.position ? r.position[1] : 0);
      const rz = typeof r.z === 'number' ? r.z : (r.position ? r.position[2] : 0.12);
      const yaw = typeof r.yaw === 'number' ? r.yaw : 0.0;

      const pCenter = project(rx, ry, rz);
      const rColor = robotPalette[r.robot_id] || '#0284C7';
      const isFailed = r.status === 'FAILED' || r.is_failed;

      // Chassis Body
      ctx.beginPath();
      ctx.arc(pCenter.px, pCenter.py, 8, 0, 2 * Math.PI);
      ctx.fillStyle = isFailed ? '#DC2626' : rColor;
      ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Heading indicator
      const frontDist = 0.5;
      const fx = rx + frontDist * Math.cos(yaw);
      const fy = ry + frontDist * Math.sin(yaw);
      const pFront = project(fx, fy, rz);
      ctx.strokeStyle = '#FACC15';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(pCenter.px, pCenter.py);
      ctx.lineTo(pFront.px, pFront.py);
      ctx.stroke();

      // Overhead Tag
      const pTag = project(rx, ry, rz + 0.6);
      ctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
      ctx.fillRect(pTag.px - 24, pTag.py - 12, 48, 14);
      ctx.strokeStyle = rColor;
      ctx.lineWidth = 1;
      ctx.strokeRect(pTag.px - 24, pTag.py - 12, 48, 14);

      ctx.fillStyle = isFailed ? '#EF4444' : '#FFFFFF';
      ctx.font = 'bold 9px monospace';
      ctx.fillText(`${r.robot_id} [${isFailed ? 'FAIL' : r.status || 'OK'}]`, pTag.px - 20, pTag.py - 2);
    }
  }, [
    camRotX,
    camRotZ,
    camZoom,
    camPanX,
    camPanY,
    effectiveRobots,
    activeRoute,
    obstacles,
  ]);

  // Simulation Controls Actions
  const handleStartSim = async () => {
    await postSimStart();
    setActionNotice('PyBullet Simulation STARTED');
    loadStatus();
  };

  const handleStopSim = async () => {
    await postSimStop();
    setActionNotice('PyBullet Simulation STOPPED');
    loadStatus();
  };

  const handleResetSim = async () => {
    await postSimReset();
    setObstacles([]);
    setActionNotice('PyBullet Simulation RESET to 4 corners');
    loadStatus();
  };

  const handleAddObstacle = async () => {
    // Parse chosen RF node to coords
    const parts = obstacleNode.split('_');
    const r = parseInt(parts[1], 10) || 3;
    const c = parseInt(parts[2], 10) || 5;
    const x = Number((X_MIN + c * SPACING_X).toFixed(2));
    const y = Number((Y_MIN + r * SPACING_Y).toFixed(2));

    const obsId = `OBS_${Date.now() % 1000}`;
    await postSimObstacle(x, y, obsId);
    setObstacles((prev) => [...prev, { id: obsId, x, y }]);
    setActionNotice(`Dynamic obstacle placed at ${obstacleNode} (${x}m, ${y}m)`);
  };

  const handleFailRobot = async () => {
    const res = await postSimFailRobot(targetRobotToFail);
    setActionNotice(`Triggered simulated hardware failure on ${targetRobotToFail}`);
    loadStatus();
  };

  const handleRecoverRobot = async () => {
    await postSimRecoverRobot(targetRobotToFail);
    setActionNotice(`Recovered AMR ${targetRobotToFail}`);
    loadStatus();
  };

  // Camera presets
  const setPresetIsometric = () => {
    setCamRotX(55);
    setCamRotZ(-40);
    setCamZoom(24);
    setCamPanX(0);
    setCamPanY(0);
  };

  const setPresetTopDown = () => {
    setCamRotX(85);
    setCamRotZ(0);
    setCamZoom(26);
    setCamPanX(0);
    setCamPanY(0);
  };

  const setPresetSide = () => {
    setCamRotX(25);
    setCamRotZ(-90);
    setCamZoom(22);
    setCamPanX(0);
    setCamPanY(0);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Simulation Command Toolbar */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)',
          padding: '14px 18px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        {/* Left: Sim Engine status & run controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>
              SIMULATION ENGINE
            </div>
            <div style={{ fontSize: 14, fontWeight: 800, color: '#38BDF8' }}>
              ● PyBullet Physics (Windows Native)
            </div>
          </div>

          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={handleStartSim}
              style={{
                background: '#16A34A',
                color: '#FFF',
                border: 'none',
                borderRadius: 'var(--r-sm)',
                padding: '6px 12px',
                fontWeight: 700,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              ▶ RUN
            </button>
            <button
              onClick={handleStopSim}
              style={{
                background: '#D97706',
                color: '#FFF',
                border: 'none',
                borderRadius: 'var(--r-sm)',
                padding: '6px 12px',
                fontWeight: 700,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              ⏸ STOP
            </button>
            <button
              onClick={handleResetSim}
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 12px',
                fontWeight: 600,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              ↺ RESET
            </button>
          </div>
        </div>

        {/* Center: Dynamic Obstacle & Failure Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {/* Add Obstacle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select
              value={obstacleNode}
              onChange={(e) => setObstacleNode(e.target.value)}
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 8px',
                fontSize: 12,
              }}
            >
              <option value="RF_5_2">Aisle RF_5_2</option>
              <option value="RF_4_5">Aisle RF_4_5</option>
              <option value="RF_3_5">Aisle RF_3_5</option>
              <option value="RF_2_8">Aisle RF_2_8</option>
              <option value="RF_1_10">Aisle RF_1_10</option>
            </select>
            <button
              onClick={handleAddObstacle}
              style={{
                background: '#EAB308',
                color: '#000',
                border: 'none',
                borderRadius: 'var(--r-sm)',
                padding: '6px 10px',
                fontWeight: 700,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              + ADD OBSTACLE
            </button>
          </div>

          {/* Fail Robot */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <select
              value={targetRobotToFail}
              onChange={(e) => setTargetRobotToFail(e.target.value)}
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 8px',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              <option value="R1">R1 (Top-Left)</option>
              <option value="R2">R2 (Top-Right)</option>
              <option value="R3">R3 (Bottom-Left)</option>
              <option value="R4">R4 (Bottom-Right)</option>
            </select>
            <button
              onClick={handleFailRobot}
              style={{
                background: '#DC2626',
                color: '#FFF',
                border: 'none',
                borderRadius: 'var(--r-sm)',
                padding: '6px 10px',
                fontWeight: 700,
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              ⚠ FAIL ROBOT
            </button>
            <button
              onClick={handleRecoverRobot}
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 10px',
                fontSize: 12,
                cursor: 'pointer',
              }}
            >
              RECOVER
            </button>
          </div>
        </div>

        {/* Right: Camera Presets */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            onClick={setPresetIsometric}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 10px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Isometric
          </button>
          <button
            onClick={setPresetTopDown}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 10px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Top-Down
          </button>
          <button
            onClick={setPresetSide}
            style={{
              background: 'var(--bg-subtle)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 10px',
              fontSize: 11,
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Side
          </button>
        </div>
      </div>

      {/* Action Notice feedback if any */}
      {actionNotice && (
        <div
          style={{
            padding: '8px 14px',
            background: 'rgba(56, 189, 248, 0.1)',
            border: '1px solid rgba(56, 189, 248, 0.3)',
            borderRadius: 'var(--r-xs)',
            fontSize: 12,
            color: '#38BDF8',
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <span>ℹ {actionNotice}</span>
          <button
            onClick={() => setActionNotice('')}
            style={{ background: 'none', border: 'none', color: '#38BDF8', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Main 3D Canvas Viewport */}
      <div
        style={{
          position: 'relative',
          background: '#080C14',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)',
          overflow: 'hidden',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          cursor: 'grab',
          boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
        }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        onContextMenu={(e) => e.preventDefault()}
      >
        <canvas
          ref={canvasRef}
          width={1100}
          height={540}
          style={{ width: '100%', height: 'auto', display: 'block' }}
        />

        {/* HUD Info Badges */}
        <div
          style={{
            position: 'absolute',
            top: 12,
            left: 12,
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 'var(--r-xs)',
            padding: '10px 14px',
            fontSize: 11,
            color: 'var(--text-secondary)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <div style={{ fontWeight: 800, color: '#FFFFFF', marginBottom: 4 }}>
            3D WAREHOUSE SIMULATION (PYBULLET)
          </div>
          <div>78 Racks (13×6) | 98 RF Nodes | 4 AMRs</div>
          <div>Mode: {simStatus?.gui_mode ? 'Hardware OpenGL (Native GUI Window)' : 'Headless Synchronized'}</div>
          <div>Controls: Left-drag to Orbit, Right-drag to Pan, Scroll to Zoom</div>
        </div>

        {/* AMR Telemetry Overlay */}
        <div
          style={{
            position: 'absolute',
            bottom: 12,
            left: 12,
            background: 'rgba(15, 23, 42, 0.85)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 'var(--r-xs)',
            padding: '8px 12px',
            display: 'flex',
            gap: 16,
            backdropFilter: 'blur(4px)',
          }}
        >
          {effectiveRobots.map((r: any) => (
            <div key={r.robot_id} style={{ fontSize: 11 }}>
              <div style={{ fontWeight: 700, color: '#38BDF8' }}>{r.robot_id}</div>
              <div style={{ color: 'var(--text-muted)' }}>Node: {r.current_node || r.node_id}</div>
              <div style={{ color: r.status === 'FAILED' ? '#EF4444' : '#10B981' }}>
                {r.status || 'OK'}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
