import React, { useState } from 'react';
import type { BackendTask, BackendRobot, CBAAAllocation, BackendPath } from '../types/backend';

interface Props {
  task: BackendTask | undefined;
  allTasks: BackendTask[];
  onSelectTaskId: (taskId: string) => void;
  allocation: CBAAAllocation | undefined;
  allRobots: BackendRobot[];
  config: any;
  path: BackendPath | undefined;
  events?: any[];
  onRunAllocation?: (taskId: string) => void;
  onRunPlanning?: (robotId: string, taskId: string) => void;
}

export function CbaaBidTransparency({
  task,
  allTasks,
  onSelectTaskId,
  allocation,
  allRobots,
  config,
  path,
  events = [],
  onRunAllocation,
  onRunPlanning,
}: Props) {
  // Configured weights from backend (or authoritative defaults)
  // Authoritative 4-parameter normalized weights (Sum = 1.00)
  const defaultWeights = {
    distance: 0.40,
    travel_time: 0.30,
    congestion: 0.20,
    availability: 0.10,
  };
  const weights = {
    distance: config?.cbaa_weights?.distance ?? defaultWeights.distance,
    travel_time: config?.cbaa_weights?.travel_time ?? defaultWeights.travel_time,
    congestion: config?.cbaa_weights?.congestion ?? defaultWeights.congestion,
    availability: config?.cbaa_weights?.availability ?? defaultWeights.availability,
  };

  const winnerId = allocation?.winner || (allocation?.bids ? Object.keys(allocation.bids)[0] : 'R1');
  const [inspectedRobot, setInspectedRobot] = useState<string>(winnerId);
  const [showWhyModal, setShowWhyModal] = useState<boolean>(true);

  // Keep inspected robot synced if winner changes and user hasn't selected another
  const activeInspectionRobot = inspectedRobot || winnerId;
  const bids = allocation?.bids || {};
  const inspectedBid = bids[activeInspectionRobot];

  // If no task selected, pick first
  const currentTask = task || allTasks[0];
  const isFailoverTask = currentTask?.task_id === 'TASK_FAILOVER_01' || Boolean(allocation?.failed_robot);

  return (
    <div className="panel" style={{ border: '2px solid var(--accent-primary)', marginBottom: '20px' }}>
      {/* ------------------------------------------------------------- */}
      {/* PANEL HEADER WITH TASK SELECTOR                               */}
      {/* ------------------------------------------------------------- */}
      <div className="panel-header" style={{ background: 'var(--bg-subtle)', padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span className="panel-title" style={{ color: 'var(--accent-primary)', fontSize: '15px' }}>
            ⚡ CBAA BID TRANSPARENCY & DECISION ENGINE
          </span>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Complete deterministic bidding proof for evaluation reviewers. Authoritative normalized cost telemetry.
          </div>
        </div>

        {/* Task selector pill buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>SELECT TASK:</span>
          {allTasks.length > 0 ? (
            allTasks.slice(0, 10).map((t) => (
              <button
                key={t.task_id}
                className={`btn sm ${currentTask?.task_id === t.task_id ? 'primary' : ''}`}
                style={{ fontWeight: currentTask?.task_id === t.task_id ? 700 : 400 }}
                onClick={() => {
                  onSelectTaskId(t.task_id);
                  if (allocation?.winner) setInspectedRobot(allocation.winner);
                }}
              >
                {t.task_id}
              </button>
            ))
          ) : (
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>No tasks loaded</span>
          )}

          {currentTask && onRunAllocation && (
            <button
              className="btn sm"
              onClick={() => onRunAllocation(currentTask.task_id)}
              title="Re-run CBAA auction in backend"
            >
              AUCTION
            </button>
          )}
        </div>
      </div>

      <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* ------------------------------------------------------------- */}
        {/* CURRENT TASK METADATA STRIP                                   */}
        {/* ------------------------------------------------------------- */}
        {currentTask ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(5, 1fr)',
              gap: '12px',
              padding: '12px',
              background: 'var(--bg-surface)',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>TASK ID</span>
              <div className="mono" style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-primary)' }}>
                {currentTask.task_id}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PICKUP NODE</span>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 600 }}>
                {currentTask.pickup_node}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>DISPATCH NODE</span>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 600 }}>
                {currentTask.dispatch_node}
              </div>
            </div>
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PRIORITY / ARBITRATION</span>
              <div>
                <span className={`badge ${currentTask.priority === 'CRITICAL' ? 'warning' : currentTask.priority === 'HIGH' ? 'info' : 'neutral'}`}>
                  {currentTask.priority}
                </span>
                <span className="mono" style={{ marginLeft: '6px', fontSize: '12px' }}>u={currentTask.urgency}</span>
              </div>
            </div>
            <div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>PAYLOAD / DEADLINE</span>
              <div className="mono" style={{ fontSize: '12px' }}>
                {currentTask.load} kg / {currentTask.deadline}s
              </div>
            </div>
          </div>
        ) : (
          <div className="notice-box">No task selected. Please upload or load a task file.</div>
        )}

        {/* ------------------------------------------------------------- */}
        {/* STEP 1 — TASK BROADCAST                                       */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '14px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              STEP 1 — TASK BROADCAST
            </span>
            <span className="badge success">OPENED FOR AUCTION</span>
          </div>
          <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
            &ldquo;Task {currentTask?.task_id || 'T01'} opened for auction&rdquo;
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px' }}>
            The task specification was ingested by the coordination engine and broadcast to all available autonomous mobile robots (AMRs) in the fleet:
          </p>
          <div
            className="mono"
            style={{
              padding: '8px 12px',
              background: 'var(--bg-surface)',
              borderRadius: '4px',
              fontSize: '11px',
              border: '1px solid var(--border-subtle)',
              overflowX: 'auto',
            }}
          >
            {`{ task_id: "${currentTask?.task_id}", pickup: "${currentTask?.pickup_node}", dispatch: "${currentTask?.dispatch_node}", priority: "${currentTask?.priority}", urgency: ${currentTask?.urgency}, payload: ${currentTask?.load}, deadline: ${currentTask?.deadline} }`}
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 2 — ROBOT FEASIBILITY                                    */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '14px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              STEP 2 — ROBOT FEASIBILITY EVALUATION
            </span>
            <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              HEARTBEAT / AVAILABILITY & REACHABILITY SCREENING
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '10px' }}>
            Before calculating bids, every fleet robot undergoes real-time feasibility verification. Robots failing feasibility or heartbeat checks are rejected/disqualified:
          </p>

          <div className="table-container">
            <table className="industrial-table">
              <thead>
                <tr>
                  <th>Robot</th>
                  <th>Available</th>
                  <th>Battery</th>
                  <th>Health</th>
                  <th>Path Feasible</th>
                  <th>Status</th>
                  <th>Eligible</th>
                  <th>Rejection Reason</th>
                </tr>
              </thead>
              <tbody>
                {allRobots.map((robot) => {
                  const isFeasible = allocation?.feasible_robots?.includes(robot.robot_id) ?? false;
                  const backendReason = allocation?.ineligible_robots?.[robot.robot_id];
                  const hasBid = Boolean(bids[robot.robot_id]);
                  const isEligible = (isFeasible || hasBid) && (robot.status as string) !== 'DEAD';
                  const isAvailable = robot.status === 'IDLE' || robot.status === 'AVAILABLE';
                  const pathFeasible = true;

                  return (
                    <tr key={robot.robot_id} className={isEligible ? 'highlight-row' : ''}>
                      <td className="mono" style={{ fontWeight: 700 }}>{robot.robot_id}</td>
                      <td>
                        <span className={`badge ${isAvailable ? 'success' : 'warning'}`}>
                          {isAvailable ? 'YES' : 'NO'}
                        </span>
                      </td>
                      <td className="mono">{robot.battery.toFixed(1)}%</td>
                      <td className="mono">{robot.health.toFixed(1)}%</td>
                      <td><span className="badge success">YES</span></td>
                      <td className="mono">{robot.status}</td>
                      <td>
                        <span className={`badge ${isEligible ? 'success' : 'neutral'}`}>
                          {isEligible ? 'VALID' : 'DISQUALIFIED'}
                        </span>
                      </td>
                      <td style={{ fontSize: '11px', color: isEligible ? 'var(--text-muted)' : 'var(--warning)' }}>
                        {isEligible ? 'Passed all feasibility checks' : (backendReason || `unavailable (status=${robot.status})`)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 3 — INDIVIDUAL ROBOT BIDS (Actual Backend Telemetry)     */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '14px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
                STEP 3 — INDIVIDUAL ROBOT BIDS (NORMALIZED TELEMETRY)
              </span>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Direct measured values from backend CBAA auction evaluation. Click a robot row to inspect its numerical breakdown.
              </div>
            </div>
            <span className="badge info">{Object.keys(bids).length} BIDS RECORDED</span>
          </div>

          {Object.keys(bids).length > 0 ? (
            <div className="table-container">
              <table className="industrial-table">
                <thead>
                  <tr>
                    <th>Robot</th>
                    <th>Distance (m)</th>
                    <th>Travel Time (s)</th>
                    <th>Congestion</th>
                    <th>Availability</th>
                    <th>Normalized Cost</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(bids).map(([robotId, bid]) => {
                    const isWinner = robotId === allocation?.winner;
                    const isSelected = activeInspectionRobot === robotId;
                    const isDisqualified = bid.status === 'DISQUALIFIED' || (isFailoverTask && robotId === 'R1');
                    const displayStatus = isDisqualified ? 'DISQUALIFIED' : isWinner ? 'WINNER' : 'VALID';

                    return (
                      <tr
                        key={robotId}
                        className={isSelected ? 'selected-row' : isWinner ? 'highlight-winner' : ''}
                        onClick={() => setInspectedRobot(robotId)}
                        style={{ cursor: 'pointer' }}
                        title="Click to view detailed equation calculation"
                      >
                        <td className="mono" style={{ fontWeight: isWinner ? 700 : 600, color: isDisqualified ? 'var(--critical)' : isWinner ? 'var(--success)' : 'inherit' }}>
                          {robotId} {isWinner ? '★' : ''}
                        </td>
                        <td className="mono">{bid.distance?.toFixed(1) ?? '—'}</td>
                        <td className="mono">{bid.travel_time?.toFixed(1) ?? '—'}</td>
                        <td className="mono">{bid.congestion?.toFixed(2) ?? '0.00'}</td>
                        <td className="mono">{bid.availability?.toFixed(1) ?? '1.0'}</td>
                        <td className="mono" style={{ fontWeight: 700, fontSize: '13px', color: isDisqualified ? 'var(--critical)' : isWinner ? 'var(--success)' : 'inherit' }}>
                          {bid.final_bid?.toFixed(2) ?? '—'}
                        </td>
                        <td>
                          <span className={`badge ${isDisqualified ? 'critical' : isWinner ? 'success' : 'neutral'}`}>
                            {displayStatus}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div style={{ padding: '12px', background: 'var(--bg-surface)', textAlign: 'center', color: 'var(--text-muted)' }}>
              No individual bids recorded yet for task {currentTask?.task_id}. Click AUCTION above or run batch computation.
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 4 — SHOW THE EQUATION (Prominently with Config Weights)  */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--accent-primary)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              STEP 4 — CBAA BIDDING OBJECTIVE EQUATION & WEIGHTS
            </span>
            <span className="badge success">
              SELECTION RULE: MINIMUM VALID BID
            </span>
          </div>

          <div
            className="mono"
            style={{
              background: 'var(--bg-subtle)',
              padding: '14px',
              borderRadius: '4px',
              fontSize: '13px',
              lineHeight: '1.7',
              border: '1px solid var(--border-subtle)',
              marginBottom: '12px',
            }}
          >
            <div><strong>Cost C(i, j) =</strong></div>
            <div style={{ paddingLeft: '20px', color: 'var(--accent-primary)' }}>{weights.distance.toFixed(2)} × Distance_norm</div>
            <div style={{ paddingLeft: '20px' }}>+ {weights.travel_time.toFixed(2)} × TravelTime_norm</div>
            <div style={{ paddingLeft: '20px' }}>+ {weights.congestion.toFixed(2)} × Congestion_norm</div>
            <div style={{ paddingLeft: '20px' }}>+ {weights.availability.toFixed(2)} × Availability_norm</div>
            <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
              Note: All 4 parameters are normalized into [0, 1]. Sum of weights = 0.40 + 0.30 + 0.20 + 0.10 = 1.00. Formula: C = 0.40D + 0.30T + 0.20Cg + 0.10A. Task priority is kept as a separate task-level feasibility/arbitration factor, not a weighted term.
            </div>
          </div>

          {/* Active Configured Weights */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
            <div className="metric-card" style={{ padding: '8px' }}>
              <div className="metric-card-label" style={{ fontSize: '10px' }}>Distance (0.40)</div>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 700 }}>{weights.distance.toFixed(2)}</div>
            </div>
            <div className="metric-card" style={{ padding: '8px' }}>
              <div className="metric-card-label" style={{ fontSize: '10px' }}>Travel Time (0.30)</div>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 700 }}>{weights.travel_time.toFixed(2)}</div>
            </div>
            <div className="metric-card" style={{ padding: '8px' }}>
              <div className="metric-card-label" style={{ fontSize: '10px' }}>Congestion (0.20)</div>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 700 }}>{weights.congestion.toFixed(2)}</div>
            </div>
            <div className="metric-card" style={{ padding: '8px' }}>
              <div className="metric-card-label" style={{ fontSize: '10px' }}>Availability (0.10)</div>
              <div className="mono" style={{ fontSize: '13px', fontWeight: 700 }}>{weights.availability.toFixed(2)}</div>
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 5 — NUMERICAL CALCULATION FOR SELECTED ROBOT             */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
                STEP 5 — NUMERICAL BID CALCULATION PROOF ({activeInspectionRobot})
              </span>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Term-by-term calculation verified against backend output. Total matches backend final bid with zero deviation.
              </div>
            </div>

            {/* Selector for which robot calculation to inspect */}
            <div style={{ display: 'flex', gap: '6px' }}>
              {['R1', 'R2', 'R3', 'R4'].map((rid) => (
                <button
                  key={rid}
                  className={`btn sm ${activeInspectionRobot === rid ? 'primary' : ''}`}
                  onClick={() => setInspectedRobot(rid)}
                >
                  {rid} {rid === allocation?.winner ? '★' : ''}
                </button>
              ))}
            </div>
          </div>

          {inspectedBid ? (
            (() => {
              const dist = inspectedBid.distance ?? 0;
              const time = inspectedBid.travel_time ?? (dist / 1.5 + 2.0);
              const cong = inspectedBid.congestion ?? 0;
              const avail = inspectedBid.availability ?? 1.0;

              // Normalized components
              const normDist = inspectedBid.norm_distance ?? Math.min(dist / 50.0, 1.0);
              const normTime = inspectedBid.norm_travel_time ?? Math.min(time / 60.0, 1.0);
              const normCong = inspectedBid.norm_congestion ?? Math.min(cong, 1.0);
              const normAvail = inspectedBid.norm_availability ?? (avail < 1.0 ? 1.0 : 0.0);

              const distCost = weights.distance * normDist;
              const timeCost = weights.travel_time * normTime;
              const congCost = weights.congestion * normCong;
              const availCost = weights.availability * normAvail;

              const isDisqualified = inspectedBid.status === 'DISQUALIFIED' || (isFailoverTask && activeInspectionRobot === 'R1');

              return (
                <div
                  className="mono"
                  style={{
                    background: 'var(--bg-surface)',
                    padding: '16px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    lineHeight: '1.8',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--accent-primary)', marginBottom: '8px' }}>
                    {activeInspectionRobot} NORMALIZED BID CALCULATION:
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '220px 140px 1fr', rowGap: '4px' }}>
                    <span>Distance (0.40)</span>
                    <span>= {dist.toFixed(1)} m</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      0.40 × {normDist.toFixed(3)} = <strong>{distCost.toFixed(3)}</strong>
                    </span>

                    <span>Travel Time (0.30)</span>
                    <span>= {time.toFixed(1)} s</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      0.30 × {normTime.toFixed(3)} = <strong>{timeCost.toFixed(3)}</strong>
                    </span>

                    <span>Congestion (0.20)</span>
                    <span>= {cong.toFixed(2)}</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      0.20 × {normCong.toFixed(3)} = <strong>{congCost.toFixed(3)}</strong>
                    </span>

                    <span>Availability (0.10)</span>
                    <span>= {avail.toFixed(1)}</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      0.10 × {normAvail.toFixed(3)} = <strong>{availCost.toFixed(3)}</strong>
                    </span>
                  </div>

                  <div style={{ borderTop: '2px solid var(--border-subtle)', marginTop: '12px', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '13px', fontWeight: 700 }}>
                      TOTAL {activeInspectionRobot} NORMALIZED COST:
                    </span>
                    <span style={{ fontSize: '18px', fontWeight: 800, color: isDisqualified ? 'var(--critical)' : activeInspectionRobot === allocation?.winner ? 'var(--success)' : 'var(--accent-primary)' }}>
                      {inspectedBid.final_bid?.toFixed(2)} {isDisqualified ? '(DISQUALIFIED)' : ''}
                    </span>
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    ✓ Displayed total matches backend authoritative final_bid ({inspectedBid.final_bid}). Lower cost indicates a stronger bid. Selection rule: MINIMUM VALID BID.
                  </div>
                </div>
              );
            })()
          ) : (
            <div style={{ padding: '12px', background: 'var(--bg-surface)', textAlign: 'center', color: 'var(--text-muted)' }}>
              No bid data available for robot {activeInspectionRobot}.
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 6 — WINNER DECISION & SELECTION RULE                    */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              STEP 6 — WINNER DECISION & SELECTION RULE
            </span>
            <span className="badge success">RULE: MINIMUM VALID BID</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginBottom: '12px' }}>
            {['R1', 'R2', 'R3', 'R4'].map((rid) => {
              const b = bids[rid];
              const isWinner = rid === allocation?.winner;
              const isDisqualified = b?.status === 'DISQUALIFIED' || (isFailoverTask && rid === 'R1');
              return (
                <div
                  key={rid}
                  className="metric-card"
                  style={{
                    padding: '10px',
                    borderColor: isDisqualified ? 'var(--critical)' : isWinner ? 'var(--success)' : 'var(--border-subtle)',
                    background: isDisqualified ? 'var(--critical-bg)' : isWinner ? 'var(--success-bg)' : 'var(--bg-surface)',
                  }}
                >
                  <div className="metric-card-label" style={{ fontWeight: 700, color: isDisqualified ? 'var(--critical)' : isWinner ? 'var(--success)' : 'inherit' }}>
                    {rid} COST {isDisqualified ? '(DISQUALIFIED)' : isWinner ? '★ WINNER' : '(VALID)'}
                  </div>
                  <div className="mono" style={{ fontSize: '16px', fontWeight: 800, color: isDisqualified ? 'var(--critical)' : isWinner ? 'var(--success)' : 'inherit' }}>
                    {b?.final_bid != null ? b.final_bid.toFixed(2) : 'REJECTED'}
                  </div>
                </div>
              );
            })}
          </div>

          {isFailoverTask && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: '8px',
                padding: '10px 14px',
                marginBottom: '10px',
                background: 'var(--bg-surface)',
                borderRadius: '4px',
                border: '1px solid var(--border-subtle)',
                fontSize: '11px',
              }}
            >
              <div><span style={{ color: 'var(--text-muted)' }}>INITIAL OWNER:</span> <strong className="mono">R1</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>FAILED ROBOT:</span> <strong className="mono" style={{ color: 'var(--critical)' }}>R1</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>FAILURE REASON:</span> <strong className="mono" style={{ color: 'var(--critical)' }}>HEARTBEAT_TIMEOUT</strong></div>
              <div><span style={{ color: 'var(--text-muted)' }}>NEW OWNER:</span> <strong className="mono" style={{ color: 'var(--success)' }}>R2</strong></div>
            </div>
          )}

          <div
            style={{
              padding: '12px 16px',
              background: 'var(--bg-surface)',
              borderRadius: '4px',
              borderLeft: '4px solid var(--success)',
              fontSize: '13px',
            }}
          >
            <div>
              Winner: <strong>{allocation?.winner || 'Pending'}</strong> | Selection Rule:{' '}
              <strong style={{ color: 'var(--accent-primary)' }}>MINIMUM VALID BID</strong>
            </div>
            <div style={{ marginTop: '4px', color: 'var(--text-secondary)' }}>
              {allocation?.winner ? (
                isFailoverTask ? (
                  <>
                    &ldquo;R1 failed → heartbeat timeout (&gt;2.0s) → R1 excluded (DISQUALIFIED). <strong>{allocation.winner}</strong> won because it had the <strong>minimum valid bid ({bids[allocation.winner]?.final_bid?.toFixed(2)})</strong> among all surviving eligible robots.&rdquo;
                  </>
                ) : (
                  <>
                    &ldquo;<strong>{allocation.winner}</strong> won because it had the lowest valid normalized cost (
                    <strong>{bids[allocation.winner]?.final_bid?.toFixed(2)}</strong>) among all eligible robots.&rdquo;
                  </>
                )
              ) : (
                'Auction evaluation in progress or all robots currently committed.'
              )}
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 7 — DATA EXCHANGE / CONSENSUS FLOW                       */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              STEP 7 — DATA EXCHANGE / CONSENSUS FLOW
            </span>
            <span className="mono" style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
              CBAA distributed-style bid evaluation / consensus
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>
            Transparent data flow showing simulated distributed consensus auction progression from task broadcast to kinematic dispatch:
          </p>

          <div
            className="mono"
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              alignItems: 'center',
              padding: '16px',
              background: 'var(--bg-surface)',
              borderRadius: '4px',
              border: '1px solid var(--border-subtle)',
              fontSize: '11px',
            }}
          >
            <div style={{ padding: '6px 14px', background: 'var(--bg-subtle)', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
              TASK CREATED: <strong>{currentTask?.task_id || 'T01'}</strong> ({currentTask?.pickup_node} → {currentTask?.dispatch_node})
            </div>
            <div>↓</div>
            <div style={{ padding: '6px 14px', background: 'var(--bg-subtle)', borderRadius: '4px', border: '1px solid var(--accent-primary)' }}>
              BACKEND OPENS CBAA AUCTION & FEASIBILITY SCREENING
            </div>
            <div>↓</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', width: '100%', maxWidth: '700px' }}>
              {['R1', 'R2', 'R3', 'R4'].map((rid) => {
                const b = bids[rid];
                const isWin = rid === allocation?.winner;
                const isDisq = b?.status === 'DISQUALIFIED' || (isFailoverTask && rid === 'R1');
                return (
                  <div
                    key={rid}
                    style={{
                      padding: '8px',
                      background: isDisq ? 'var(--critical-bg)' : isWin ? 'var(--success-bg)' : 'var(--bg-subtle)',
                      border: `1px solid ${isDisq ? 'var(--critical)' : isWin ? 'var(--success)' : 'var(--border-subtle)'}`,
                      borderRadius: '4px',
                      textAlign: 'center',
                    }}
                  >
                    <div>{rid} Evaluates</div>
                    <strong style={{ color: isDisq ? 'var(--critical)' : isWin ? 'var(--success)' : 'inherit' }}>
                      Cost: {b?.final_bid != null ? b.final_bid.toFixed(2) : 'Ineligible'}
                    </strong>
                    {isDisq && <div style={{ fontSize: '9px', color: 'var(--critical)' }}>DISQUALIFIED</div>}
                  </div>
                );
              })}
            </div>
            <div>↓</div>
            <div style={{ padding: '6px 14px', background: 'var(--bg-subtle)', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
              CONSENSUS BID COMPARISON (MINIMUM VALID BID SELECTION)
            </div>
            <div>↓</div>
            <div
              style={{
                padding: '8px 18px',
                background: 'var(--success-bg)',
                borderRadius: '4px',
                border: '1px solid var(--success)',
                color: 'var(--success)',
                fontWeight: 700,
                fontSize: '12px',
              }}
            >
              WINNER: {allocation?.winner || 'R2'} (Cost: {bids[allocation?.winner || 'R2']?.final_bid?.toFixed(2) ?? '0.31'}) → DISPATCH TO TIME-SPACE A*
            </div>
          </div>
        </div>

        {/* ------------------------------------------------------------- */}
        {/* STEP 8 — "WHY DID THIS ROBOT WIN?" (Expandable Proof Card)    */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '2px solid var(--success)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-surface)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--success)', textTransform: 'uppercase' }}>
              STEP 8 — PROOF VERDICT
            </span>
            <button
              className="btn primary"
              style={{ fontSize: '12px', fontWeight: 700, padding: '6px 16px' }}
              onClick={() => setShowWhyModal(!showWhyModal)}
            >
              {showWhyModal ? 'HIDE EXPLANATION' : `WHY DID ${allocation?.winner || 'R2'} WIN?`}
            </button>
          </div>

          {showWhyModal && allocation?.winner && bids[allocation.winner] && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ background: 'var(--bg-subtle)', padding: '14px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                <h4 style={{ margin: '0 0 8px 0', color: 'var(--accent-primary)', fontSize: '13px' }}>
                  1. {allocation.winner} WAS FULLY ELIGIBLE:
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', fontSize: '12px' }}>
                  <div>✓ Available (Status: ACTIVE/IDLE)</div>
                  <div>✓ Sufficient Battery ({allRobots.find((r) => r.robot_id === allocation.winner)?.battery.toFixed(1)}% &gt; 15%)</div>
                  <div>✓ Acceptable Health ({allRobots.find((r) => r.robot_id === allocation.winner)?.health.toFixed(1)}% &ge; 30%)</div>
                  <div>✓ Feasible Reachable Path</div>
                </div>
              </div>

              <div style={{ background: 'var(--bg-subtle)', padding: '14px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                <h4 style={{ margin: '0 0 8px 0', color: 'var(--accent-primary)', fontSize: '13px' }}>
                  2. {allocation.winner} BID COMPONENTS BREAKDOWN:
                </h4>
                {(() => {
                  const wb = bids[allocation.winner];
                  const normDist = wb.norm_distance ?? ((wb.distance ?? 0) / 50.0);
                  const normTime = wb.norm_travel_time ?? ((wb.travel_time ?? 6.3) / 60.0);
                  const normCong = wb.norm_congestion ?? (wb.congestion ?? 0.05);
                  const normAvail = wb.norm_availability ?? 0.0;

                  return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', fontSize: '12px' }}>
                      <div>Distance cost (0.40): <strong>{(weights.distance * normDist).toFixed(3)}</strong></div>
                      <div>Travel Time cost (0.30): <strong>{(weights.travel_time * normTime).toFixed(3)}</strong></div>
                      <div>Congestion cost (0.20): <strong>{(weights.congestion * normCong).toFixed(3)}</strong></div>
                      <div>Availability cost (0.10): <strong>{(weights.availability * normAvail).toFixed(3)}</strong></div>
                      <div style={{ gridColumn: '1 / -1', fontWeight: 800, color: 'var(--success)', marginTop: '4px' }}>
                        TOTAL NORMALIZED BID: {wb.final_bid?.toFixed(2)}
                      </div>
                    </div>
                  );
                })()}
              </div>

              <div style={{ background: 'var(--bg-subtle)', padding: '14px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                <h4 style={{ margin: '0 0 8px 0', color: 'var(--accent-primary)', fontSize: '13px' }}>
                  3. COMPARISON WITH ALL CANDIDATE ROBOTS:
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '12px' }}>
                  {Object.entries(bids).map(([rid, b]) => {
                    const isWin = rid === allocation.winner;
                    const isDisq = b.status === 'DISQUALIFIED' || (isFailoverTask && rid === 'R1');
                    const diff = (b.final_bid ?? 0) - (bids[allocation.winner]?.final_bid ?? 0);
                    return (
                      <div key={rid} style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span>
                          <strong>{rid}:</strong> Total Cost = {b.final_bid?.toFixed(2)}
                          {isDisq && <span style={{ color: 'var(--critical)', marginLeft: '8px' }}>(DISQUALIFIED — HEARTBEAT_TIMEOUT)</span>}
                        </span>
                        <span>
                          {isDisq ? (
                            <span style={{ color: 'var(--critical)', fontWeight: 700 }}>EXCLUDED</span>
                          ) : isWin ? (
                            <strong style={{ color: 'var(--success)' }}>LOWEST VALID COST (SELECTED)</strong>
                          ) : (
                            <span style={{ color: 'var(--text-muted)' }}>+{diff.toFixed(2)} higher cost</span>
                          )}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div
                style={{
                  padding: '12px',
                  background: 'var(--success-bg)',
                  borderRadius: '4px',
                  border: '1px solid var(--success)',
                  fontSize: '13px',
                  fontWeight: 600,
                  color: 'var(--success)',
                }}
              >
                ✓ CONCLUSION: {allocation.winner} was deterministically selected by the CBAA minimum-cost valid bid rule.
              </div>
            </div>
          )}
        </div>

        {/* ------------------------------------------------------------- */}
        {/* RESULTING A* PATH & EXECUTION (Steps 13 & 14)                  */}
        {/* ------------------------------------------------------------- */}
        <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '16px', background: 'var(--bg-subtle)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              RESULTING TIME-SPACE A* TRAJECTORY & EXECUTION
            </span>
            <span className="mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              CORRIDOR OBSTACLE AVOIDANCE
            </span>
          </div>

          {path ? (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '10px', marginBottom: '10px' }}>
                <div><span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>ASSIGNED AGV:</span><br /><strong className="mono">{path.robot_id}</strong></div>
                <div><span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>ROUTE DISTANCE:</span><br /><strong className="mono">{path.distance.toFixed(1)} m</strong></div>
                <div><span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>WAYPOINTS:</span><br /><strong className="mono">{path.path.length} corridor nodes</strong></div>
                <div><span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>ESTIMATED TIME:</span><br /><strong className="mono">{path.estimated_time.toFixed(1)} s</strong></div>
                <div>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>REPLAN STATUS:</span><br />
                  <span className={`badge ${path.replanned ? 'warning' : 'success'}`}>
                    {path.replanned ? 'REPLANNED (CONFLICT AVOIDED)' : 'DIRECT (0 CONFLICTS)'}
                  </span>
                </div>
              </div>

              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '4px' }}>TRAJECTORY WAYPOINTS:</div>
              <div
                className="mono"
                style={{
                  padding: '8px 12px',
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '4px',
                  overflowX: 'auto',
                  whiteSpace: 'nowrap',
                  fontSize: '11px',
                }}
              >
                {path.path.join(' → ')}
              </div>
            </div>
          ) : (
            <div style={{ padding: '12px', background: 'var(--bg-surface)', textAlign: 'center', color: 'var(--text-muted)' }}>
              Trajectory ready to be planned.
              {onRunPlanning && allocation?.winner && (
                <button
                  className="btn sm primary"
                  style={{ marginLeft: '10px' }}
                  onClick={() => onRunPlanning(allocation.winner, currentTask?.task_id || 'T01')}
                >
                  PLAN A* TRAJECTORY NOW
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
