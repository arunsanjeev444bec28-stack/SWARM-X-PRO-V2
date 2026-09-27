import React from 'react';
import type { CBAAAllocation, BackendRobot } from '../types/backend';

interface Props {
  allocation?: CBAAAllocation;
  config?: any;
  robots: BackendRobot[];
}

function rowCls(status: string, winner: boolean): string {
  if (winner) return 'winner-row';
  if (status === 'DISQUALIFIED') return 'fault-row';
  return '';
}

function statusBadge(status: string, winner: boolean) {
  if (winner) return <span className="badge badge-winner" style={{ fontSize: 12, padding: '4px 8px' }}>WINNER</span>;
  if (status === 'DISQUALIFIED') return <span className="badge badge-disq" style={{ fontSize: 12, padding: '4px 8px' }}>DISQUALIFIED</span>;
  return <span className="badge badge-neutral" style={{ fontSize: 12, padding: '4px 8px' }}>VALID</span>;
}

function fmt(v: number | undefined, dec = 2): string {
  return v != null ? v.toFixed(dec) : '—';
}

export function CbaaPanel({ allocation, config }: Props) {
  const W = {
    distance: config?.cbaa_weights?.distance ?? 0.40,
    travel_time: config?.cbaa_weights?.travel_time ?? 0.30,
    congestion: config?.cbaa_weights?.congestion ?? 0.20,
    availability: config?.cbaa_weights?.availability ?? 0.10,
  };

  const apiBids = allocation?.bids;
  const hasBids = apiBids && Object.keys(apiBids).length > 0;

  const bids = hasBids
    ? Object.entries(apiBids).map(([rid, b]) => ({
        robot_id: rid,
        distance: b.distance ?? 0,
        travel_time: b.travel_time ?? 0,
        congestion: b.norm_congestion ?? b.congestion ?? 0,
        availability: b.norm_availability ?? b.availability ?? 1,
        cost: b.final_bid ?? b.total_bid ?? b.cost ?? 0,
        status: b.status || (allocation?.winner === rid ? 'WINNER' : 'VALID'),
        winner: allocation?.winner === rid || b.winner === true,
      }))
    : [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      {/* Weight strip */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 10,
          padding: '10px 16px',
          background: 'var(--bg-subtle)',
          borderBottom: '1.5px solid var(--border-subtle)',
          fontSize: 13,
          alignItems: 'center',
        }}
      >
        <span style={{ fontWeight: 800, color: 'var(--text-primary)' }}>DECENTRALIZED CBAA WEIGHTS:</span>
        <span style={{ padding: '3px 8px', background: 'var(--bg-surface)', borderRadius: 4, border: '1px solid var(--border-medium)', fontWeight: 600 }}>
          Distance <strong>{(W.distance * 100).toFixed(0)}%</strong>
        </span>
        <span style={{ padding: '3px 8px', background: 'var(--bg-surface)', borderRadius: 4, border: '1px solid var(--border-medium)', fontWeight: 600 }}>
          Travel Time <strong>{(W.travel_time * 100).toFixed(0)}%</strong>
        </span>
        <span style={{ padding: '3px 8px', background: 'var(--bg-surface)', borderRadius: 4, border: '1px solid var(--border-medium)', fontWeight: 600 }}>
          Congestion <strong>{(W.congestion * 100).toFixed(0)}%</strong>
        </span>
        <span style={{ padding: '3px 8px', background: 'var(--bg-surface)', borderRadius: 4, border: '1px solid var(--border-medium)', fontWeight: 600 }}>
          Availability <strong>{(W.availability * 100).toFixed(0)}%</strong>
        </span>
        <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: 13, fontWeight: 700 }}>
          Rule: MINIMUM VALID BID
        </span>
      </div>

      {/* Bid table or empty state */}
      {!hasBids ? (
        <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>
            NO ACTIVE BIDS
          </div>
          <div style={{ fontSize: 13 }}>
            No task auction is currently in progress. Create and dispatch a task from the Tasks tab to view live peer-to-peer bids calculated by the 4 AMR edge agents.
          </div>
        </div>
      ) : (
        <table className="cbaa-table">
          <thead>
            <tr>
              <th>AMR</th>
              <th>Distance</th>
              <th>Travel Time</th>
              <th>Congestion</th>
              <th>Availability</th>
              <th>Normalized Cost</th>
              <th>Auction Decision</th>
            </tr>
          </thead>
          <tbody>
            {bids.map((b) => (
              <tr key={b.robot_id} className={rowCls(b.status, b.winner)}>
                <td>
                  <span
                    className="mono"
                    style={{
                      fontWeight: 800,
                      fontSize: 15,
                      color: b.winner
                        ? 'var(--success-text)'
                        : b.status === 'DISQUALIFIED'
                        ? 'var(--fault-text)'
                        : 'var(--text-primary)',
                    }}
                  >
                    {b.robot_id}
                    {b.winner ? ' ★' : ''}
                  </span>
                </td>
                <td className="mono" style={{ fontSize: 14 }}>
                  {fmt(b.distance, 1)} m
                </td>
                <td className="mono" style={{ fontSize: 14 }}>
                  {fmt(b.travel_time, 1)} s
                </td>
                <td className="mono" style={{ fontSize: 14 }}>
                  {fmt(b.congestion, 2)}
                </td>
                <td className="mono" style={{ fontSize: 14 }}>
                  {fmt(b.availability, 1)}
                </td>
                <td
                  className="mono"
                  style={{
                    fontWeight: 800,
                    fontSize: 15,
                    color: b.winner
                      ? 'var(--success-text)'
                      : b.status === 'DISQUALIFIED'
                      ? 'var(--fault-text)'
                      : undefined,
                  }}
                >
                  {fmt(b.cost, 4)}
                </td>
                <td>{statusBadge(b.status, b.winner)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
