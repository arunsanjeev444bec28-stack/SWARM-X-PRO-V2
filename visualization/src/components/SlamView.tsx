import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  fetchSlamMap,
  postSlamStart,
  postSlamPause,
  postSlamReset,
  postSlamClearTrajectory,
  postSlamSelectRobot,
} from '../services/api';

interface Props {
  liveSlamData?: any;
}

const ROBOT_COLORS: Record<string, string> = {
  R1: '#38BDF8', // Cyan
  R2: '#10B981', // Emerald Green
  R3: '#F97316', // Orange
  R4: '#A855F7', // Purple
};

export function SlamView({ liveSlamData }: Props) {
  const [selectedRobot, setSelectedRobot] = useState<string>('ALL');
  const [slamData, setSlamData] = useState<any>(null);
  const [isUpdating, setIsUpdating] = useState<boolean>(true);
  const [zoom, setZoom] = useState<number>(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Fetch SLAM state on selection or mount
  const loadSlamState = useCallback(async (rid: string) => {
    try {
      const res = await fetchSlamMap(rid, 2);
      if (res) {
        setSlamData(res);
      }
    } catch (e) {
      console.error('Failed to fetch SLAM map', e);
    }
  }, []);

  useEffect(() => {
    loadSlamState(selectedRobot);
    const interval = setInterval(() => {
      loadSlamState(selectedRobot);
    }, 1000);
    return () => clearInterval(interval);
  }, [selectedRobot, loadSlamState]);

  // Sync with live WebSocket SLAM updates
  useEffect(() => {
    if (liveSlamData) {
      if (selectedRobot === 'ALL' || liveSlamData.robot_id === selectedRobot) {
        setSlamData((prev: any) => ({
          ...prev,
          ...liveSlamData,
        }));
      }
    }
  }, [liveSlamData, selectedRobot]);

  // View control handlers
  const handleZoomIn = () => setZoom((z) => Math.min(3.0, z * 1.25));
  const handleZoomOut = () => setZoom((z) => Math.max(0.6, z * 0.8));
  const handleResetView = () => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  };
  const handleFitMap = () => {
    setZoom(1.05);
    setPan({ x: 0, y: 0 });
  };

  // Render Occupancy Grid onto HTML5 Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !slamData) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width_m = 35.0, height_m = 15.0, min_x = -17.5, min_y = -7.5 } =
      slamData.dimensions || {};
    const occupancy = slamData.occupancy_grid;

    const cw = canvas.width;
    const ch = canvas.height;

    // Helper: world coordinates (meters) to canvas pixels with zoom & pan
    const worldToPixel = (wx: number, wy: number) => {
      const basePx = ((wx - min_x) / width_m) * cw;
      const basePy = ch - ((wy - min_y) / height_m) * ch;
      const px = cw / 2 + (basePx - cw / 2 + pan.x) * zoom;
      const py = ch / 2 + (basePy - ch / 2 + pan.y) * zoom;
      return { px, py };
    };

    // 1. Clear background (UNKNOWN space)
    ctx.fillStyle = '#0B0F19';
    ctx.fillRect(0, 0, cw, ch);

    // Coordinate grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    for (let gx = -15; gx <= 15; gx += 5) {
      const p1 = worldToPixel(gx, -7.5);
      const p2 = worldToPixel(gx, 7.5);
      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.stroke();
    }
    for (let gy = -5; gy <= 5; gy += 5) {
      const p1 = worldToPixel(-17.5, gy);
      const p2 = worldToPixel(17.5, gy);
      ctx.beginPath();
      ctx.moveTo(p1.px, p1.py);
      ctx.lineTo(p2.px, p2.py);
      ctx.stroke();
    }

    // 2. Draw explored cells if available
    if (occupancy && occupancy.cells && occupancy.cols && occupancy.rows) {
      const cols = occupancy.cols;
      const rows = occupancy.rows;
      const cellW = (cw / cols) * zoom;
      const cellH = (ch / rows) * zoom;
      const cells: number[] = occupancy.cells;

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const val = cells[r * cols + c];
          if (val === -1) {
            continue; // UNKNOWN
          }
          // Compute screen position of cell
          const wx = min_x + (c / cols) * width_m;
          const wy = min_y + (r / rows) * height_m;
          const pt = worldToPixel(wx, wy);

          if (val === 0) {
            // FREE space (traversed by LiDAR)
            ctx.fillStyle = '#1E293B';
            ctx.fillRect(pt.px, pt.py - cellH, cellW + 0.6, cellH + 0.6);
          } else if (val >= 100) {
            // OCCUPIED surface (rack/wall hit)
            ctx.fillStyle = '#38BDF8';
            ctx.fillRect(pt.px, pt.py - cellH, cellW + 0.6, cellH + 0.6);
          }
        }
      }
    }

    // 3. Draw Trajectories
    if (selectedRobot === 'ALL' && slamData.all_trajectories) {
      Object.entries(slamData.all_trajectories).forEach(([rid, traj]: [string, any]) => {
        if (Array.isArray(traj) && traj.length > 1) {
          ctx.beginPath();
          const p0 = worldToPixel(traj[0][0], traj[0][1]);
          ctx.moveTo(p0.px, p0.py);
          for (let i = 1; i < traj.length; i++) {
            const pt = worldToPixel(traj[i][0], traj[i][1]);
            ctx.lineTo(pt.px, pt.py);
          }
          ctx.strokeStyle = ROBOT_COLORS[rid] || '#06B6D4';
          ctx.lineWidth = 2.0;
          ctx.stroke();
        }
      });
    } else {
      const trajectory: number[][] = slamData.trajectory || [];
      if (trajectory.length > 1) {
        ctx.beginPath();
        const p0 = worldToPixel(trajectory[0][0], trajectory[0][1]);
        ctx.moveTo(p0.px, p0.py);
        for (let i = 1; i < trajectory.length; i++) {
          const pt = worldToPixel(trajectory[i][0], trajectory[i][1]);
          ctx.lineTo(pt.px, pt.py);
        }
        ctx.strokeStyle = ROBOT_COLORS[selectedRobot] || '#06B6D4';
        ctx.lineWidth = 2.0;
        ctx.stroke();
      }
    }

    // 4. Draw LiDAR Hit Points
    const lidarPoints: number[][] = slamData.lidar_points || [];
    ctx.fillStyle = '#10B981';
    for (const pt of lidarPoints) {
      const p = worldToPixel(pt[0], pt[1]);
      ctx.beginPath();
      ctx.arc(p.px, p.py, 1.6 * zoom, 0, 2 * Math.PI);
      ctx.fill();
    }

    // 5. Draw Forward Obstacle if detected
    if (slamData.forward_obstacle && slamData.forward_obstacle.point) {
      const op = worldToPixel(
        slamData.forward_obstacle.point[0],
        slamData.forward_obstacle.point[1]
      );
      ctx.strokeStyle = '#EF4444';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(op.px, op.py, 9 * zoom, 0, 2 * Math.PI);
      ctx.stroke();
      ctx.fillStyle = '#EF4444';
      ctx.font = 'bold 11px monospace';
      ctx.fillText(
        `OBSTACLE (${slamData.forward_obstacle.distance.toFixed(2)}m)`,
        op.px + 12,
        op.py - 4
      );
    }

    // 6. Draw Robot Poses (Position & Heading)
    const drawRobot = (rid: string, pose: any) => {
      if (!pose) return;
      const rp = worldToPixel(pose.x, pose.y);
      const color = ROBOT_COLORS[rid] || '#38BDF8';

      // Scan aura
      const grad = ctx.createRadialGradient(rp.px, rp.py, 4, rp.px, rp.py, 50 * zoom);
      grad.addColorStop(0, 'rgba(6, 182, 212, 0.30)');
      grad.addColorStop(1, 'rgba(6, 182, 212, 0.0)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(rp.px, rp.py, 50 * zoom, 0, 2 * Math.PI);
      ctx.fill();

      // Chassis circle
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(rp.px, rp.py, 7 * zoom, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 2;
      ctx.stroke();

      // Heading arrow
      const arrowLength = 18 * zoom;
      const hx = rp.px + arrowLength * Math.cos(pose.yaw);
      const hy = rp.py - arrowLength * Math.sin(pose.yaw);
      ctx.strokeStyle = '#FACC15';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.moveTo(rp.px, rp.py);
      ctx.lineTo(hx, hy);
      ctx.stroke();

      // Label
      ctx.fillStyle = '#FFFFFF';
      ctx.font = 'bold 11px monospace';
      ctx.fillText(rid, rp.px + 10, rp.py + 4);
    };

    if (selectedRobot === 'ALL' && slamData.all_poses) {
      Object.entries(slamData.all_poses).forEach(([rid, pose]) => {
        drawRobot(rid, pose);
      });
    } else if (slamData.pose) {
      drawRobot(slamData.robot_id || selectedRobot, slamData.pose);
    }

    // 7. Scale bar overlay (Bottom Left)
    const scaleLenMeters = 5.0;
    const pStart = worldToPixel(-15.0, -6.5);
    const pEnd = worldToPixel(-15.0 + scaleLenMeters, -6.5);
    const barWidthPx = Math.abs(pEnd.px - pStart.px);

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(pStart.px, pStart.py);
    ctx.lineTo(pStart.px + barWidthPx, pStart.py);
    ctx.stroke();

    ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.font = 'bold 10px monospace';
    ctx.fillText(`${scaleLenMeters}m SCALE`, pStart.px, pStart.py - 6);
  }, [slamData, selectedRobot, zoom, pan]);

  const handleRobotChange = async (rid: string) => {
    setSelectedRobot(rid);
    if (rid !== 'ALL') {
      await postSlamSelectRobot(rid);
    }
    loadSlamState(rid);
  };

  const handleStart = async () => {
    await postSlamStart();
    setIsUpdating(true);
    loadSlamState(selectedRobot);
  };

  const handlePause = async () => {
    await postSlamPause();
    setIsUpdating(false);
  };

  const handleResetMap = async () => {
    await postSlamReset(selectedRobot === 'ALL' ? undefined : selectedRobot);
    loadSlamState(selectedRobot);
  };

  const handleClearTrajectory = async () => {
    await postSlamClearTrajectory(selectedRobot === 'ALL' ? undefined : selectedRobot);
    loadSlamState(selectedRobot);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Controls & Metrics Header */}
      <div
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
              SLAM Robot View
            </div>
            <select
              value={selectedRobot}
              onChange={(e) => handleRobotChange(e.target.value)}
              style={{
                background: 'var(--bg-subtle)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                padding: '6px 12px',
                fontWeight: 700,
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              <option value="ALL">ALL (Fleet Combined View)</option>
              <option value="R1">AMR R1 (Top-Left)</option>
              <option value="R2">AMR R2 (Top-Right)</option>
              <option value="R3">AMR R3 (Bottom-Left)</option>
              <option value="R4">AMR R4 (Bottom-Right)</option>
            </select>
          </div>

          {/* View Scaling & Navigation Controls */}
          <div style={{ display: 'flex', gap: 6, alignItems: 'center', borderLeft: '1px solid var(--border-subtle)', paddingLeft: 12 }}>
            <button
              onClick={handleFitMap}
              className="btn btn-sm"
              style={{ fontWeight: 700, fontSize: 11, background: 'var(--bg-subtle)' }}
              title="Automatically fit warehouse into view"
            >
              FIT MAP
            </button>
            <button
              onClick={handleZoomIn}
              className="btn btn-sm"
              style={{ fontWeight: 800, fontSize: 13, padding: '4px 10px' }}
              title="Zoom in"
            >
              +
            </button>
            <button
              onClick={handleZoomOut}
              className="btn btn-sm"
              style={{ fontWeight: 800, fontSize: 13, padding: '4px 10px' }}
              title="Zoom out"
            >
              -
            </button>
            <button
              onClick={handleResetView}
              className="btn btn-sm"
              style={{ fontWeight: 600, fontSize: 11, background: 'var(--bg-subtle)' }}
              title="Reset zoom and center"
            >
              RESET VIEW
            </button>
          </div>

          <div style={{ display: 'flex', gap: 6, alignItems: 'center', borderLeft: '1px solid var(--border-subtle)', paddingLeft: 12 }}>
            <button
              onClick={handleStart}
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
              ▶ RESUME
            </button>
            <button
              onClick={handlePause}
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
              ⏸ PAUSE
            </button>
            <button
              onClick={handleResetMap}
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
              ↺ RESET MAP
            </button>
            <button
              onClick={handleClearTrajectory}
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
              ⌫ CLEAR TRAIL
            </button>
          </div>
        </div>

        {/* Real-time SLAM Metrics */}
        <div style={{ display: 'flex', gap: 18, alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>STATUS</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: isUpdating ? '#10B981' : '#F59E0B' }}>
              ● {slamData?.status || (isUpdating ? 'RUNNING' : 'PAUSED')}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>SCANS</div>
            <div style={{ fontSize: 15, fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
              {slamData?.scan_count ?? 0}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>COVERAGE</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: '#38BDF8', fontFamily: 'var(--font-mono)' }}>
              {slamData?.coverage_percent ?? 0.0}%
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>RESOLUTION</div>
            <div style={{ fontSize: 15, fontWeight: 800, fontFamily: 'var(--font-mono)' }}>
              {slamData?.map_resolution ?? 0.10} m
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-muted)' }}>SCALE (X x Y)</div>
            <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              31.2 x 12.0 m
            </div>
          </div>
        </div>
      </div>

      {/* Main Canvas Display with Precise 35:15 Aspect Ratio */}
      <div
        style={{
          position: 'relative',
          background: '#0B0F19',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-md)',
          overflow: 'hidden',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          boxShadow: '0 4px 14px rgba(0,0,0,0.5)',
          minHeight: 450,
        }}
      >
        <canvas
          ref={canvasRef}
          width={1050}
          height={450}
          style={{ width: '100%', height: 'auto', display: 'block', maxHeight: '72vh' }}
        />

        {/* Legend Overlay */}
        <div
          style={{
            position: 'absolute',
            bottom: 12,
            right: 12,
            background: 'rgba(15, 23, 42, 0.90)',
            border: '1px solid rgba(255,255,255,0.12)',
            borderRadius: 'var(--r-xs)',
            padding: '8px 14px',
            fontSize: 11,
            display: 'flex',
            gap: 16,
            backdropFilter: 'blur(6px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, background: '#38BDF8', display: 'inline-block' }} />
            <span>Occupied Racks/Walls</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, background: '#1E293B', display: 'inline-block' }} />
            <span>Free Aisles</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, background: '#0B0F19', display: 'inline-block', border: '1px solid #334155' }} />
            <span>Unknown Space</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#10B981', display: 'inline-block' }} />
            <span>LiDAR Reflection</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#FACC15', display: 'inline-block' }} />
            <span>AMR Heading</span>
          </div>
        </div>
      </div>
    </div>
  );
}
