import type {
  BackendPath,
  BackendRobot,
  BackendTask,
  BenchmarkResult,
  CBAAAllocation,
  ConflictRecord,
  DeadlockState,
  GazeboStatus,
  SpaceTimeReservation,
  WarehouseNode,
  SimulationState,
  SimulationWarehouse,
} from '../types/backend';

const host = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'localhost';
export const apiBaseUrl = `http://${host}:8000`;

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return response.json() as Promise<T>;
  }

  return response.text() as unknown as T;
}

async function safeRequest<T>(path: string, options?: RequestInit): Promise<T | null> {
  try {
    return await request<T>(path, options);
  } catch {
    return null;
  }
}

export const fetchHealth = () => safeRequest<{ status: string }>('/api/health');
export const fetchApiState = () => safeRequest<any>('/api/state');
export const fetchMetrics = () => safeRequest<any>('/api/metrics');
export const fetchTasks = () => safeRequest<BackendTask[]>('/api/tasks');
export const fetchRobots = () => safeRequest<BackendRobot[]>('/api/robots');
export const fetchWarehouse = () => safeRequest<any>('/api/warehouse');
export const fetchWarehouseModel = () => safeRequest<any>('/api/warehouse');
export const fetchAllocations = () => safeRequest<CBAAAllocation[]>('/api/allocations');
export const fetchPaths = () => safeRequest<BackendPath[]>('/api/paths');
export const fetchReservations = () => safeRequest<SpaceTimeReservation[]>('/api/reservations');
export const fetchConflicts = () => safeRequest<ConflictRecord[]>('/api/conflicts');
export const fetchDeadlocks = () => safeRequest<DeadlockState>('/api/deadlocks');
export const fetchCongestion = () => safeRequest<any[]>('/api/congestion');
export const fetchObstacles = () => safeRequest<any[]>('/api/obstacles');
export const fetchFailures = () => safeRequest<any[]>('/api/failures');
export const fetchAiStatus = () => safeRequest<any>('/api/ai/status');
export const fetchAiMetrics = () => safeRequest<any>('/api/ai/metrics');
export const fetchAiFeatures = () => safeRequest<any>('/api/ai/features');
export const fetchEvents = () => safeRequest<any[]>('/api/events');
export const fetchBenchmark = () => safeRequest<BenchmarkResult>('/api/benchmark');
export const fetchGazeboStatus = () => safeRequest<GazeboStatus>('/api/gazebo/status');
export const fetchConfig = () => safeRequest<any>('/api/config');
export const fetchPeerStatus = () => safeRequest<any>('/api/peer/status');
export const fetchPeerMessages = () => safeRequest<any[]>('/api/peer/messages');

export const postTask = (task: Partial<BackendTask>) =>
  request<any>('/api/tasks', { method: 'POST', body: JSON.stringify(task) });

export const postBatchTasks = async (tasks: Partial<BackendTask>[]) => {
  try {
    return await request<any>('/api/tasks/batch', { method: 'POST', body: JSON.stringify(tasks) });
  } catch {
    const results: any[] = [];
    for (const task of tasks) {
      results.push(await postTask(task));
    }
    return results;
  }
};

export const postBenchmark = () =>
  request<BenchmarkResult>('/api/benchmark/run', { method: 'POST', body: JSON.stringify({}) });

export const postAllocation = (taskId: string) =>
  request<any>(`/api/allocation/run?task_id=${encodeURIComponent(taskId)}`, { method: 'POST' });

export const postPlanning = (robotId: string, taskId: string) =>
  request<any>(
    `/api/planning/run?robot_id=${encodeURIComponent(robotId)}&task_id=${encodeURIComponent(taskId)}`,
    { method: 'POST' }
  );

export const postAiTrain = () =>
  request<any>('/api/ai/train', { method: 'POST', body: JSON.stringify({}) });

export const postPredict = (payload: any) =>
  request<any>('/api/ai/predict', { method: 'POST', body: JSON.stringify(payload) });

export const postInitRealWarehouse = () =>
  request<any>('/api/warehouse/real/init', { method: 'POST', body: JSON.stringify({}) });

export const postSimulationStart = () =>
  request<any>('/api/simulation/start', { method: 'POST', body: JSON.stringify({}) });

export const postSimulationStop = () =>
  request<any>('/api/simulation/stop', { method: 'POST', body: JSON.stringify({}) });

export const postSimulationReset = () =>
  request<any>('/api/simulation/reset', { method: 'POST', body: JSON.stringify({}) });

export const postReauction = (failedRobotId: string) =>
  request<any>('/api/reauction', {
    method: 'POST',
    body: JSON.stringify({ failed_robot_id: failedRobotId }),
  });

export const postAddObstacle = (obstacle: any) =>
  request<any>('/api/obstacles', { method: 'POST', body: JSON.stringify(obstacle) });

export const postAddFailure = (failure: any) =>
  request<any>('/api/failures', { method: 'POST', body: JSON.stringify(failure) });

export const fetchFailoverDemo = () => safeRequest<any>('/api/demo/failover');

export const postFailoverDemoRun = () =>
  request<any>('/api/demo/failover/run', { method: 'POST', body: JSON.stringify({}) });

export const fetchSimulationState = () => safeRequest<SimulationState>('/api/simulation/state');
export const fetchSimulationWarehouse = () => safeRequest<SimulationWarehouse>('/api/simulation/warehouse');

// PyBullet 3D Simulation Controls
export const fetchSimulationStatus = () => safeRequest<any>('/api/simulation/status');
export const fetchSimulationTelemetry = () => safeRequest<any>('/api/simulation/telemetry');
export const postSimStart = () => request<any>('/api/simulation/start', { method: 'POST' });
export const postSimStop = () => request<any>('/api/simulation/stop', { method: 'POST' });
export const postSimReset = () => request<any>('/api/simulation/reset', { method: 'POST' });
export const postSimObstacle = (x: number, y: number, obstacle_id: string = 'OBS_1') =>
  request<any>('/api/simulation/obstacle', {
    method: 'POST',
    body: JSON.stringify({ x, y, obstacle_id }),
  });
export const postSimFailRobot = (robot_id: string) =>
  request<any>('/api/simulation/fail_robot', {
    method: 'POST',
    body: JSON.stringify({ robot_id }),
  });
export const postSimRecoverRobot = (robot_id: string) =>
  request<any>('/api/simulation/recover_robot', {
    method: 'POST',
    body: JSON.stringify({ robot_id }),
  });

// 2D Occupancy Grid SLAM Controls
export const fetchSlamStatus = (robot_id?: string) =>
  safeRequest<any>(`/api/slam/status${robot_id ? `?robot_id=${encodeURIComponent(robot_id)}` : ''}`);
export const fetchSlamMap = (robot_id?: string, scale_down: number = 2) =>
  safeRequest<any>(
    `/api/slam/map?scale_down=${scale_down}${robot_id ? `&robot_id=${encodeURIComponent(robot_id)}` : ''}`
  );
export const postSlamStart = () => request<any>('/api/slam/start', { method: 'POST' });
export const postSlamPause = () => request<any>('/api/slam/pause', { method: 'POST' });
export const postSlamReset = (robot_id?: string) =>
  request<any>('/api/slam/reset', {
    method: 'POST',
    body: JSON.stringify(robot_id ? { robot_id } : {}),
  });
export const postSlamClearTrajectory = (robot_id?: string) =>
  request<any>('/api/slam/clear_trajectory', {
    method: 'POST',
    body: JSON.stringify(robot_id ? { robot_id } : {}),
  });
export const postSlamSelectRobot = (robot_id: string) =>
  request<any>('/api/slam/select_robot', {
    method: 'POST',
    body: JSON.stringify({ robot_id }),
  });

// Task File Ingestion & Validation
export const postValidateTasksFile = (content: string, filename: string = 'tasks.csv') =>
  request<any>('/api/tasks/import/validate', {
    method: 'POST',
    body: JSON.stringify({ content, filename }),
  });

export const postDispatchTasksFile = (tasks: any[]) =>
  request<any>('/api/tasks/import/dispatch', {
    method: 'POST',
    body: JSON.stringify({ tasks }),
  });

// Performance Benchmark Endpoints
export const fetchBenchmarkResults = () => safeRequest<any>('/api/benchmark/results');
export const postRunBenchmark = (task_file?: string, inject_obstacle: boolean = true, fail_robot_id?: string) =>
  request<any>('/api/benchmark/run', {
    method: 'POST',
    body: JSON.stringify({ task_file, inject_obstacle, fail_robot_id }),
  });

export const connectWebSocket = (
  onMessage: (data: any) => void,
  onStatus?: (status: 'CONNECTED' | 'DISCONNECTED') => void
) => {
  const socket = new WebSocket(`ws://${host}:8000/ws`);
  socket.onopen = () => onStatus?.('CONNECTED');
  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);
      onMessage(message);
    } catch (e) {
      console.error('Failed to parse WebSocket message', e);
    }
  };
  socket.onerror = (error) => console.error('WebSocket error', error);
  socket.onclose = () => onStatus?.('DISCONNECTED');
  return socket;
};
