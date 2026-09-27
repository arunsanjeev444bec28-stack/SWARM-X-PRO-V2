import React, { useCallback, useRef, useState } from 'react';
import type { BackendRobot, WarehouseNode, WarehouseData } from '../types/backend';

interface Props {
  robots: BackendRobot[];
  warehouseNodes?: WarehouseNode[];
  warehouseData?: WarehouseData | null;
  racks?: any[];
  activeRoute?: string[];
  activeTask?: {
    task_id?: string;
    pickup_node?: string;
    dispatch_node?: string;
    status?: string;
    winner?: string;
  };
  obstacles?: Array<{ node_id?: string; x?: number; y?: number }>;
  onRobotClick?: (robotId: string) => void;
  onNodeClick?: (nodeId: string) => void;
}

// 78-Rack Industrial Layout Constants (13 columns × 6 rows = 78 racks)
// 14 vertical aisles (c = 0..13) × 7 horizontal aisles (r = 0..6) = 98 RF intersection nodes
export const GRID_ROWS = 7;
export const GRID_COLS = 14;
export const SPACING_X = 64.0;
export const SPACING_Y = 56.0;
export const ORIGIN_X = 80.0;
export const ORIGIN_Y = 440.0;

// Authoritative corner RF node mapping
export const CORNER_RF_NODES = {
  R1: 'RF_6_0',   // top-left (r=6, c=0)
  R2: 'RF_6_13',  // top-right (r=6, c=13)
  R3: 'RF_0_0',   // bottom-left (r=0, c=0)
  R4: 'RF_0_13',  // bottom-right (r=0, c=13)
};

// Fallback initial 4 AMRs located at the 4 valid corner RF nodes, all AVAILABLE
export const DEFAULT_CORNER_ROBOTS: BackendRobot[] = [
  { robot_id: 'R1', node_id: 'RF_6_0', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R2', node_id: 'RF_6_13', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R3', node_id: 'RF_0_0', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
  { robot_id: 'R4', node_id: 'RF_0_13', battery: 100, temperature: 25, load: 0, health: 100, status: 'AVAILABLE' },
];

export function rfNodeToSvg(nodeId: string): { x: number; y: number } {
  try {
    const parts = nodeId.split('_');
    const r = parseInt(parts[1], 10);
    const c = parseInt(parts[2], 10);
    if (!isNaN(r) && !isNaN(c)) {
      return {
        x: ORIGIN_X + c * SPACING_X,
        y: ORIGIN_Y - r * SPACING_Y,
      };
    }
  } catch {
    // fallback
  }
  return { x: ORIGIN_X, y: ORIGIN_Y };
}

function pointsFromNodes(nodes: string[]): string {
  return nodes
    .filter(Boolean)
    .map((n) => {
      const p = rfNodeToSvg(n);
      return `${p.x},${p.y}`;
    })
    .join(' ');
}

function robotColor(status: string): string {
  const s = (status || '').toUpperCase();
  if (s === 'DEAD' || s === 'FAULT' || s === 'FAILED') return '#DC2626';
  if (s === 'ACTIVE' || s === 'MOVING' || s === 'DISPATCHING' || s === 'TRANSPORTING') return '#2563EB';
  if (s === 'LOADING') return '#D97706';
  return '#16A34A'; // IDLE / AVAILABLE
}

export function WarehouseMap({
  robots,
  warehouseData,
  activeRoute,
  activeTask,
  obstacles = [],
  onRobotClick,
  onNodeClick,
}: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [scale, setScale] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragging = useRef(false);
  const lastPt = useRef({ x: 0, y: 0 });
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredRobot, setHoveredRobot] = useState<string | null>(null);

  // Map layer toggle controls
  const [showRfNodes, setShowRfNodes] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [showRackLabels, setShowRackLabels] = useState(true);

  // Effective robots: Use real robots from backend or initial corner robots
  const displayRobots = robots && robots.length >= 4 ? robots : DEFAULT_CORNER_ROBOTS;

  // Real route: only display if route actually exists
  const hasRealRoute = Boolean(activeRoute && activeRoute.length > 1);
  const effectiveRoute = hasRealRoute ? (activeRoute as string[]) : [];

  const pickupNode = activeTask?.pickup_node || '';
  const destNode = activeTask?.dispatch_node || '';

  const pickupCoord = pickupNode ? rfNodeToSvg(pickupNode) : null;
  const destCoord = destNode ? rfNodeToSvg(destNode) : null;

  // Zoom & Pan handlers
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setScale((s) => Math.min(3, Math.max(0.5, s - e.deltaY * 0.001)));
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    lastPt.current = { x: e.clientX, y: e.clientY };
  }, []);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - lastPt.current.x;
    const dy = e.clientY - lastPt.current.y;
    lastPt.current = { x: e.clientX, y: e.clientY };
    setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
  }, []);

  const onMouseUp = useCallback(() => {
    dragging.current = false;
  }, []);

  const fitWarehouse = () => {
    setScale(1);
    setPan({ x: 0, y: 0 });
  };
  const zoomIn = () => setScale((s) => Math.min(3, s + 0.2));
  const zoomOut = () => setScale((s) => Math.max(0.5, s - 0.2));

  // Build the 78 racks (6 rows × 13 columns = 78 racks)
  // Placed between aisle intersections
  const rackElements = [];
  let rackNum = 1;
  for (let r = 0; r < 6; r++) {
    for (let c = 0; c < 13; c++) {
      const centerX = ORIGIN_X + c * SPACING_X + SPACING_X / 2.0;
      const centerY = ORIGIN_Y - r * SPACING_Y - SPACING_Y / 2.0;
      const rackWidth = 44;
      const rackHeight = 32;
      const rackId = `RACK_${String(rackNum).padStart(2, '0')}`;
      rackNum++;

      rackElements.push(
        <g key={rackId} className="warehouse-rack-group">
          <rect
            x={centerX - rackWidth / 2}
            y={centerY - rackHeight / 2}
            width={rackWidth}
            height={rackHeight}
            fill="#F1F5F9"
            stroke="#94A3B8"
            strokeWidth="1.2"
            rx={3}
          />
          {/* Shelf divider line */}
          <line
            x1={centerX - rackWidth / 2 + 4}
            y1={centerY}
            x2={centerX + rackWidth / 2 - 4}
            y2={centerY}
            stroke="#CBD5E1"
            strokeWidth="1"
          />
          {showRackLabels && (
            <text
              x={centerX}
              y={centerY + 3}
              fill="#64748B"
              fontSize="8"
              fontWeight="700"
              textAnchor="middle"
              style={{ pointerEvents: 'none', userSelect: 'none' }}
            >
              {rackId.replace('RACK_', 'R')}
            </text>
          )}
        </g>
      );
    }
  }

  return (
    <div
      className="map-container"
      onWheel={handleWheel}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseUp}
      style={{ position: 'relative', overflow: 'hidden', background: '#F8FAFC', userSelect: 'none' }}
    >
      <svg
        ref={svgRef}
        className="map-svg"
        viewBox="0 0 1020 540"
        preserveAspectRatio="xMidYMid meet"
        style={{ width: '100%', height: '100%', cursor: dragging.current ? 'grabbing' : 'grab' }}
      >
        <defs>
          <filter id="routeGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>

          <marker
            id="pathArrow"
            viewBox="0 0 10 10"
            refX="6"
            refY="5"
            markerWidth="5"
            markerHeight="5"
            orient="auto-start-reverse"
          >
            <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#2563EB" />
          </marker>
        </defs>

        {/* Pan and Zoom Group */}
        <g transform={`translate(${pan.x},${pan.y}) scale(${scale})`}>
          {/* Warehouse Floor Boundary */}
          <rect
            x={ORIGIN_X - 35}
            y={ORIGIN_Y - 6 * SPACING_Y - 35}
            width={13 * SPACING_X + 70}
            height={6 * SPACING_Y + 70}
            fill="#FFFFFF"
            stroke="#CBD5E1"
            strokeWidth="2"
            rx="8"
          />

          {/* Horizontal Aisles (7 lines, r=0..6) */}
          {Array.from({ length: GRID_ROWS }).map((_, r) => {
            const y = ORIGIN_Y - r * SPACING_Y;
            return (
              <line
                key={`h-aisle-${r}`}
                x1={ORIGIN_X}
                y1={y}
                x2={ORIGIN_X + 13 * SPACING_X}
                y2={y}
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 2"
              />
            );
          })}

          {/* Vertical Aisles (14 lines, c=0..13) */}
          {Array.from({ length: GRID_COLS }).map((_, c) => {
            const x = ORIGIN_X + c * SPACING_X;
            return (
              <line
                key={`v-aisle-${c}`}
                x1={x}
                y1={ORIGIN_Y}
                x2={x}
                y2={ORIGIN_Y - 6 * SPACING_Y}
                stroke="#E2E8F0"
                strokeWidth="2"
                strokeDasharray="4 2"
              />
            );
          })}

          {/* EXACTLY 78 RACKS */}
          {rackElements}

          {/* Active Navigation Route (Real A* route on RF graph) */}
          {showRoutes && hasRealRoute && (
            <>
              <polyline
                points={pointsFromNodes(effectiveRoute)}
                fill="none"
                stroke="#BFDBFE"
                strokeWidth="8"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity="0.7"
              />
              <polyline
                className="active-path-line"
                points={pointsFromNodes(effectiveRoute)}
                fill="none"
                stroke="#2563EB"
                strokeWidth="3.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                markerEnd="url(#pathArrow)"
              />
            </>
          )}

          {/* 98 RF Intersection Nodes (14 columns × 7 rows) */}
          {showRfNodes &&
            Array.from({ length: GRID_ROWS }).map((_, r) =>
              Array.from({ length: GRID_COLS }).map((_, c) => {
                const nodeId = `RF_${r}_${c}`;
                const { x, y } = rfNodeToSvg(nodeId);
                const isHovered = hoveredNode === nodeId;
                const isPickup = nodeId === pickupNode;
                const isDest = nodeId === destNode;
                const isCorner =
                  nodeId === CORNER_RF_NODES.R1 ||
                  nodeId === CORNER_RF_NODES.R2 ||
                  nodeId === CORNER_RF_NODES.R3 ||
                  nodeId === CORNER_RF_NODES.R4;

                let fill = '#94A3B8';
                let radius = 3.5;

                if (isDest) {
                  fill = '#16A34A';
                  radius = 7;
                } else if (isPickup) {
                  fill = '#D97706';
                  radius = 7;
                } else if (isCorner) {
                  fill = '#475569';
                  radius = 5;
                } else if (isHovered) {
                  fill = '#2563EB';
                  radius = 6;
                }

                return (
                  <g
                    key={nodeId}
                    style={{ cursor: 'pointer' }}
                    onMouseEnter={() => setHoveredNode(nodeId)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={() => onNodeClick?.(nodeId)}
                  >
                    <circle cx={x} cy={y} r={12} fill="transparent" />
                    <circle
                      cx={x}
                      cy={y}
                      r={radius}
                      fill={fill}
                      stroke="#FFFFFF"
                      strokeWidth="1.5"
                    />

                    {isHovered && (
                      <g transform={`translate(${x}, ${y - 12})`}>
                        <rect x="-30" y="-18" width="60" height="18" fill="#0F172A" rx="3" />
                        <text
                          x="0"
                          y="-5"
                          fill="#FFFFFF"
                          fontSize="10"
                          fontWeight="700"
                          textAnchor="middle"
                          fontFamily="var(--font-mono)"
                        >
                          {nodeId}
                        </text>
                      </g>
                    )}
                  </g>
                );
              })
            )}

          {/* Dynamic Obstacles if present */}
          {obstacles.map((obs, idx) => {
            const coord = obs.node_id
              ? rfNodeToSvg(obs.node_id)
              : { x: obs.x ?? 0, y: obs.y ?? 0 };
            return (
              <g key={`obs-${idx}`} transform={`translate(${coord.x}, ${coord.y})`}>
                <rect x="-10" y="-10" width="20" height="20" fill="#DC2626" rx="2" opacity="0.8" />
                <text x="0" y="4" fill="#FFFFFF" fontSize="9" fontWeight="900" textAnchor="middle">
                  ✕
                </text>
              </g>
            );
          })}

          {/* Waypoint Marker: Pickup (if active task) */}
          {pickupCoord && (
            <g transform={`translate(${pickupCoord.x}, ${pickupCoord.y})`}>
              <circle r="16" fill="none" stroke="#D97706" strokeWidth="2" strokeDasharray="4 2" />
              <circle r="20" fill="#D97706" opacity="0.1" />
              <rect x="-38" y="-36" width="76" height="20" rx="3" fill="#D97706" />
              <text x="0" y="-22" fill="#FFFFFF" fontSize="11" fontWeight="800" textAnchor="middle">
                📦 PICKUP
              </text>
              <text x="0" y="-10" fill="#B45309" fontSize="10" fontWeight="700" textAnchor="middle">
                {pickupNode}
              </text>
            </g>
          )}

          {/* Waypoint Marker: Destination (if active task) */}
          {destCoord && (
            <g transform={`translate(${destCoord.x}, ${destCoord.y})`}>
              <circle r="16" fill="none" stroke="#16A34A" strokeWidth="2" strokeDasharray="4 2" />
              <circle r="20" fill="#16A34A" opacity="0.1" />
              <rect x="-42" y="-36" width="84" height="20" rx="3" fill="#16A34A" />
              <text x="0" y="-22" fill="#FFFFFF" fontSize="11" fontWeight="800" textAnchor="middle">
                🎯 DESTINATION
              </text>
              <text x="0" y="-10" fill="#15803D" fontSize="10" fontWeight="700" textAnchor="middle">
                {destNode}
              </text>
            </g>
          )}

          {/* 4 AMRs: Top-Left (R1), Top-Right (R2), Bottom-Left (R3), Bottom-Right (R4) */}
          {displayRobots.map((robot) => {
            const { x, y } = rfNodeToSvg(robot.node_id);
            const col = robotColor(robot.status);
            const isMoving =
              robot.status === 'ACTIVE' ||
              robot.status === 'MOVING' ||
              robot.status === 'DISPATCHING' ||
              robot.status === 'TRANSPORTING';

            return (
              <g
                key={robot.robot_id}
                style={{
                  transform: `translate(${x}px, ${y}px)`,
                  transition: 'transform 0.4s cubic-bezier(0.34, 1.56, 0.64, 1)',
                  cursor: 'pointer',
                }}
                onClick={() => onRobotClick?.(robot.robot_id)}
                onMouseEnter={() => setHoveredRobot(robot.robot_id)}
                onMouseLeave={() => setHoveredRobot(null)}
              >
                {/* Movement Radar Wave */}
                {isMoving && (
                  <circle
                    r="24"
                    fill="none"
                    stroke="#2563EB"
                    strokeWidth="2"
                    opacity="0.4"
                    style={{ animation: 'pulseRadar 1.8s infinite' }}
                  />
                )}

                {/* Outer shadow halo */}
                <circle r="18" fill={col} opacity="0.18" />

                {/* Robot Puck Base */}
                <circle
                  r="15"
                  fill="#FFFFFF"
                  stroke={col}
                  strokeWidth="3"
                  filter="drop-shadow(0px 2px 4px rgba(0,0,0,0.15))"
                />

                {/* AMR Identifier */}
                <text
                  x="0"
                  y="4.5"
                  fill={col}
                  fontSize="12"
                  fontWeight="900"
                  textAnchor="middle"
                  fontFamily="var(--font-mono)"
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {robot.robot_id}
                </text>

                {/* Status Pill Badge Floating Above Robot */}
                <g transform="translate(0, -22)">
                  <rect x="-30" y="-8" width="60" height="16" rx="8" fill="#0F172A" opacity="0.9" />
                  <text
                    x="0"
                    y="4"
                    fill="#FFFFFF"
                    fontSize="9"
                    fontWeight="800"
                    textAnchor="middle"
                    fontFamily="var(--font-mono)"
                  >
                    {robot.battery.toFixed(0)}% · {robot.node_id}
                  </text>
                </g>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Industrial Controls Overlay */}
      <div
        style={{
          position: 'absolute',
          top: 12,
          right: 12,
          display: 'flex',
          gap: 6,
          background: 'rgba(255,255,255,0.92)',
          padding: '6px 8px',
          borderRadius: 6,
          border: '1px solid #CBD5E1',
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          alignItems: 'center',
          zIndex: 10,
        }}
      >
        <button
          className="map-btn"
          onClick={zoomIn}
          title="Zoom +"
          style={{ padding: '4px 10px', fontSize: 13, fontWeight: 700 }}
        >
          Zoom +
        </button>
        <button
          className="map-btn"
          onClick={zoomOut}
          title="Zoom −"
          style={{ padding: '4px 10px', fontSize: 13, fontWeight: 700 }}
        >
          Zoom −
        </button>
        <button
          className="map-btn"
          onClick={fitWarehouse}
          title="Fit Warehouse"
          style={{ padding: '4px 10px', fontSize: 12, fontWeight: 700 }}
        >
          Fit Warehouse
        </button>
        <span style={{ width: 1, height: 18, background: '#CBD5E1', margin: '0 4px' }} />
        <button
          className={`map-btn ${showRfNodes ? 'active' : ''}`}
          onClick={() => setShowRfNodes((v) => !v)}
          title="Toggle RF Nodes"
          style={{ padding: '4px 8px', fontSize: 11, fontWeight: 600 }}
        >
          {showRfNodes ? 'Hide Nodes' : 'Show Nodes'}
        </button>
        <button
          className={`map-btn ${showRoutes ? 'active' : ''}`}
          onClick={() => setShowRoutes((v) => !v)}
          title="Toggle Route Display"
          style={{ padding: '4px 8px', fontSize: 11, fontWeight: 600 }}
        >
          {showRoutes ? 'Hide Routes' : 'Show Routes'}
        </button>
        <button
          className={`map-btn ${showRackLabels ? 'active' : ''}`}
          onClick={() => setShowRackLabels((v) => !v)}
          title="Toggle Rack Labels"
          style={{ padding: '4px 8px', fontSize: 11, fontWeight: 600 }}
        >
          {showRackLabels ? 'Hide Labels' : 'Show Labels'}
        </button>
      </div>

      {/* Industrial Operational Legend */}
      <div
        className="map-legend-card"
        style={{
          position: 'absolute',
          bottom: 12,
          left: 12,
          background: 'rgba(255,255,255,0.95)',
          border: '1px solid #CBD5E1',
          borderRadius: 6,
          padding: '8px 12px',
          fontSize: 11,
          boxShadow: '0 2px 6px rgba(0,0,0,0.06)',
          zIndex: 10,
        }}
      >
        <div style={{ fontWeight: 800, color: '#0F172A', marginBottom: 4 }}>
          INDUSTRIAL WAREHOUSE · 78 RACKS · 98 RF AISLE NODES
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: '#16A34A',
                border: '1px solid #FFFFFF',
              }}
            />
            <span>AMR Available (Corner Spawns)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: '#2563EB',
                border: '1px solid #FFFFFF',
              }}
            />
            <span>AMR Active / Transporting</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 12,
                height: 8,
                background: '#F1F5F9',
                border: '1px solid #94A3B8',
                borderRadius: 2,
              }}
            />
            <span>Racks (78 Shelving Units)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span
              style={{
                display: 'inline-block',
                width: 18,
                height: 3,
                background: '#2563EB',
                borderRadius: 2,
              }}
            />
            <span>A* Orthogonal Navigation Route</span>
          </div>
        </div>
      </div>
    </div>
  );
}
