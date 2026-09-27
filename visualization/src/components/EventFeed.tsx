import React from 'react';

interface Props {
  eventLog: any[];
}

function dotCls(event: any): string {
  const t = (event.event || '').toUpperCase();
  if (t.includes('FAIL') || t.includes('ERROR') || t.includes('TIMEOUT')) return 'fault';
  if (t.includes('COMPLETE') || t.includes('SUCCESS')) return 'success';
  if (t.includes('REOPEN') || t.includes('CONFLICT') || t.includes('WAITING') || t.includes('WARNING')) return 'warning';
  return 'info';
}

export function EventFeed({ eventLog }: Props) {
  const liveEvents = eventLog.slice(0, 50);

  if (liveEvents.length === 0) {
    return (
      <div style={{ padding: '24px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4 }}>
          NO RECENT EVENTS
        </div>
        <div style={{ fontSize: 12 }}>
          Event stream idle. Actions from task dispatch, CBAA consensus, or robot movement will appear here live.
        </div>
      </div>
    );
  }

  return (
    <div className="event-feed">
      {liveEvents.map((ev, i) => {
        const ts = ev.timestamp ? String(ev.timestamp).slice(11, 19) : '—';
        const detail = [
          ev.task_id ? `Task: ${ev.task_id}` : '',
          ev.robot_id ? `AMR: ${ev.robot_id}` : '',
          ev.winner ? `Winner: ${ev.winner}` : '',
          ev.pickup ? `Pickup: ${ev.pickup}` : '',
          ev.destination ? `Dest: ${ev.destination}` : '',
          ev.node_id ? `Node: ${ev.node_id}` : '',
          ev.message || ev.reason || '',
        ]
          .filter(Boolean)
          .join(' · ');

        return (
          <div key={i} className="event-item">
            <span className="event-ts">{ts}</span>
            <span className={`event-dot ${dotCls(ev)}`} />
            <div>
              <div className="event-text">{ev.event || 'EVENT'}</div>
              {detail && <div className="event-sub">{detail}</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
