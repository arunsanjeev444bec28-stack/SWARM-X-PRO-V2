import React, { useState, useRef } from 'react';
import { postValidateTasksFile, postDispatchTasksFile } from '../services/api';

interface TaskImportPanelProps {
  onTasksDispatched?: (count: number) => void;
}

export const TaskImportPanel: React.FC<TaskImportPanelProps> = ({ onTasksDispatched }) => {
  const [fileContent, setFileContent] = useState<string>('');
  const [fileName, setFileName] = useState<string>('demo_tasks.csv');
  const [validationResult, setValidationResult] = useState<any>(null);
  const [validating, setValidating] = useState<boolean>(false);
  const [dispatching, setDispatching] = useState<boolean>(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      setFileContent(text);
      validateContent(text, file.name);
    };
    reader.readAsText(file);
  };

  const handleLoadDemoWorkload = async () => {
    try {
      setValidating(true);
      setStatusMsg('Loading authoritative data/tasks/demo_tasks.csv...');
      const demoCsv = [
        'task_id,pickup_node,destination_node,priority,task_type,deadline_s',
        'TASK_001,RF_6_1,RF_2_10,HIGH,TRANSPORT,120',
        'TASK_002,RF_0_3,RF_5_12,NORMAL,DELIVERY,180',
        'TASK_003,RF_6_10,RF_1_2,CRITICAL,PICKUP,90',
        'TASK_004,RF_0_8,RF_4_5,NORMAL,TRANSFER,200',
        'TASK_005,RF_5_2,RF_1_11,HIGH,TRANSPORT,140',
        'TASK_006,RF_2_4,RF_6_9,NORMAL,DELIVERY,160',
        'TASK_007,RF_1_8,RF_5_3,CRITICAL,TRANSPORT,85',
        'TASK_008,RF_4_12,RF_0_1,NORMAL,PICKUP,220',
        'TASK_009,RF_6_4,RF_3_8,HIGH,TRANSFER,130',
        'TASK_010,RF_0_6,RF_6_7,NORMAL,DELIVERY,175',
        'TASK_011,RF_3_1,RF_2_12,HIGH,TRANSPORT,150',
        'TASK_012,RF_5_9,RF_0_4,NORMAL,PICKUP,190',
        'TASK_013,RF_1_5,RF_6_2,CRITICAL,DELIVERY,95',
        'TASK_014,RF_4_3,RF_1_10,NORMAL,TRANSPORT,210',
        'TASK_015,RF_2_8,RF_5_6,HIGH,TRANSFER,125',
        'TASK_016,RF_6_8,RF_3_5,NORMAL,DELIVERY,165',
        'TASK_017,RF_0_10,RF_4_2,HIGH,PICKUP,140',
        'TASK_018,RF_3_11,RF_0_2,CRITICAL,TRANSPORT,100',
      ].join('\n');

      setFileName('demo_tasks.csv');
      setFileContent(demoCsv);
      await validateContent(demoCsv, 'demo_tasks.csv');
    } catch (err: any) {
      setStatusMsg(`Error loading demo workload: ${err?.message || 'Failed'}`);
    } finally {
      setValidating(false);
    }
  };

  const validateContent = async (content: string, name: string) => {
    try {
      setValidating(true);
      setStatusMsg('Validating task schema, RF nodes, priorities & deadlines...');
      const res = await postValidateTasksFile(content, name);
      setValidationResult(res);
      if (res.valid) {
        setStatusMsg(`VALIDATION PASSED: ${res.valid_count} tasks verified against authoritative warehouse.`);
      } else {
        setStatusMsg(`VALIDATION FAILED: ${res.errors?.length || 0} syntax/node errors detected.`);
      }
    } catch (err: any) {
      setStatusMsg(`Validation request error: ${err?.message || 'Failed'}`);
    } finally {
      setValidating(false);
    }
  };

  const handleDispatch = async () => {
    if (!validationResult || !validationResult.valid || !validationResult.tasks) return;
    try {
      setDispatching(true);
      setStatusMsg(`Dispatching ${validationResult.tasks.length} tasks into P2P CBAA auction...`);
      const res = await postDispatchTasksFile(validationResult.tasks);
      setStatusMsg(`SUCCESS: ${res.count} tasks dispatched to AMR edge agents!`);
      onTasksDispatched?.(res.count);
    } catch (err: any) {
      setStatusMsg(`Dispatch error: ${err?.message || 'Failed'}`);
    } finally {
      setDispatching(false);
    }
  };

  return (
    <div className="panel" style={{ padding: '18px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="panel-header" style={{ padding: '0 0 12px', borderBottom: '1.5px solid var(--border-subtle)' }}>
        <div>
          <span className="panel-title">Task File Ingestion &amp; Strict Validation Engine</span>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Support for CSV / JSON task files with row-level validation against 98 RF nodes
          </div>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={handleLoadDemoWorkload} disabled={validating || dispatching}>
            📂 LOAD DEMO WORKLOAD (demo_tasks.csv)
          </button>
          <button className="btn btn-primary" onClick={() => fileInputRef.current?.click()} disabled={validating || dispatching}>
            📁 IMPORT TASK FILE
          </button>
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".csv,.json"
            onChange={handleFileUpload}
          />
        </div>
      </div>

      {statusMsg && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 6,
            fontSize: 13,
            fontWeight: 700,
            background: validationResult?.valid
              ? 'rgba(16, 185, 129, 0.1)'
              : validationResult && !validationResult.valid
              ? 'rgba(239, 68, 68, 0.1)'
              : 'rgba(56, 189, 248, 0.1)',
            borderLeft: `4px solid ${
              validationResult?.valid
                ? 'var(--success, #10b981)'
                : validationResult && !validationResult.valid
                ? 'var(--fault, #ef4444)'
                : 'var(--accent, #38bdf8)'
            }`,
            color: validationResult?.valid
              ? 'var(--success, #10b981)'
              : validationResult && !validationResult.valid
              ? 'var(--fault, #ef4444)'
              : 'var(--text-primary)',
          }}
        >
          {statusMsg}
        </div>
      )}

      {/* Validation Errors List if invalid */}
      {validationResult && !validationResult.valid && validationResult.errors?.length > 0 && (
        <div style={{ background: 'rgba(239, 68, 68, 0.08)', padding: 12, borderRadius: 6, border: '1px solid var(--fault)' }}>
          <div style={{ fontWeight: 800, color: 'var(--fault)', fontSize: 13, marginBottom: 6 }}>
            REJECTED ROWS &amp; VALIDATION ERRORS ({validationResult.errors.length}):
          </div>
          <ul style={{ margin: 0, paddingLeft: 20, fontSize: 12, color: 'var(--fault)' }}>
            {validationResult.errors.map((err: string, idx: number) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Parsed Tasks Preview Table */}
      {validationResult && validationResult.valid && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 13, fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-secondary)' }}>
              Workload Preview ({validationResult.valid_count} Validated Tasks):
            </span>
            <button
              className="btn btn-primary"
              onClick={handleDispatch}
              disabled={dispatching}
              style={{ padding: '8px 20px', fontWeight: 800 }}
            >
              {dispatching ? 'DISPATCHING TO CBAA...' : '⚡ DISPATCH ALL VALIDATED TASKS'}
            </button>
          </div>

          <div style={{ maxHeight: 240, overflowY: 'auto', border: '1px solid var(--border-subtle)', borderRadius: 6 }}>
            <table className="full-table">
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>Pickup RF Node</th>
                  <th>Destination RF Node</th>
                  <th>Priority</th>
                  <th>Type</th>
                  <th>Deadline</th>
                </tr>
              </thead>
              <tbody>
                {validationResult.tasks.map((t: any) => (
                  <tr key={t.task_id}>
                    <td><span className="mono" style={{ fontWeight: 800 }}>{t.task_id}</span></td>
                    <td><span className="mono">{t.pickup_node}</span></td>
                    <td><span className="mono">{t.destination_node}</span></td>
                    <td>
                      <span className={`badge ${t.priority === 'CRITICAL' ? 'badge-fault' : t.priority === 'HIGH' ? 'badge-warning' : 'badge-neutral'}`}>
                        {t.priority}
                      </span>
                    </td>
                    <td>{t.task_type}</td>
                    <td className="mono">{t.deadline_s}s</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
