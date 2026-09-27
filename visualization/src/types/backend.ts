export type BackendTask = {
  task_id: string;
  pickup_node: string;
  dispatch_node: string;
  priority: string;
  urgency?: number;
  deadline?: number;
  load?: number;
  energy_requirement?: number;
  status?: string;
  task_type?: string;
  winner?: string;
};

export type BackendRobot = {
  robot_id: string;
  node_id: string;
  battery: number;
  temperature: number;
  load: number;
  health: number;
  status: string;
  position?: number[];
};

export type WarehouseNode = {
  node_id: string;
  x: number;
  y: number;
  type: string;
  neighbors: string[];
  health: number;
};

export type WarehouseRack = {
  rack_id: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type WarehouseNavEdge = {
  from_node: string;
  to_node: string;
  distance: number;
  blocked: boolean;
};

export type WarehouseAisle = {
  id: string;
  type: string;
  y?: number;
  x?: number;
  x_min?: number;
  x_max?: number;
  y_min?: number;
  y_max?: number;
};

export type WarehouseData = {
  total_racks: number;
  rack_count?: number;
  total_rf_nodes: number;
  rf_node_count?: number;
  racks: WarehouseRack[];
  aisles: WarehouseAisle[];
  intersections: Array<{ id: string; x: number; y: number; neighbors: string[] }>;
  rf_nodes: Record<string, WarehouseNode>;
  edges: WarehouseNavEdge[];
  dimensions: {
    x_min: number;
    x_max: number;
    y_min: number;
    y_max: number;
    width: number;
    height: number;
  };
  corner_nodes: {
    R1: string;
    R2: string;
    R3: string;
    R4: string;
  };
};

export type PathCoordinate = {
  node_id: string;
  x: number;
  y: number;
};

export type BackendPath = {
  robot_id: string;
  task_id: string;
  path: string[];
  distance: number;
  estimated_time: number;
  replanned?: boolean;
  coordinates?: PathCoordinate[];
};

export type CBAANormalizedMetrics = {
  distance?: number;
  travel_time?: number;
  congestion?: number;
  availability?: number;
  total_cost?: number;
};

export type CBAABidDetail = {
  robot_id?: string;
  distance?: number;
  travel_time?: number;
  congestion?: number;
  availability?: number;
  norm_distance?: number;
  norm_travel_time?: number;
  norm_congestion?: number;
  norm_availability?: number;
  normalized?: CBAANormalizedMetrics;
  total_bid?: number;
  final_bid?: number;
  cost?: number;
  base_bid?: number;
  is_valid?: boolean;
  status?: string;
  reason?: string;
  winner?: boolean;
  weights?: Record<string, number>;
  temperature?: number;
  makespan_impact?: number;
  priority_benefit?: number;
  risk_penalty?: number;
};

export type CBAAAllocation = {
  task_id: string;
  winner: string;
  winning_bid?: number;
  selection_rule?: string;
  feasible_robots?: string[];
  ineligible_robots?: Record<string, string>;
  reason?: string;
  bids?: Record<string, CBAABidDetail>;
  failed_robot?: string;
  failure_reason?: string;
  initial_owner?: string;
};

export type SpaceTimeReservation = {
  robot_id: string;
  node_id: string;
  time_step: number;
  type?: string;
  task_id?: string;
};

export type ConflictRecord = {
  conflict_id?: string;
  type?: string;
  robot_1: string;
  robot_2: string;
  node?: string;
  time_step?: number;
  resolution?: string;
};

export type DeadlockState = {
  status?: string;
  active_deadlocks: any[];
  dependency_graph: Record<string, any>;
  total_deadlocks: number;
  recovered_deadlocks: number;
  failed_recoveries: number;
};

export type GazeboStatus = {
  status: string;
  live_connected: boolean;
  mode: string;
  message: string;
};

export type BenchmarkMetricSummary = {
  makespan: number;
  completed_tasks: number;
  collision_count: number;
  conflict_count?: number;
  replans?: number;
  deadlocks?: number;
  wait_fallback?: number;
};

export type BenchmarkResult = {
  measurement_type: string;
  target: string;
  historical_reference: string;
  baseline: BenchmarkMetricSummary;
  swarmx: BenchmarkMetricSummary;
  improvement_percent: number;
};

export type TaskRow = BackendTask & {
  [key: string]: string | number;
};

export type TaskDatasetValidation = {
  validRows: number;
  invalidRows: number;
  invalidNodeIds: number;
  missingFields: number;
};

export type ProofStep = {
  stage: string;
  status: 'VERIFIED' | 'ACTIVE' | 'DATA UNAVAILABLE';
  timestamp: string;
  sourceEvent: string;
  detail?: string;
};

export type DashboardSnapshot = {
  state: any;
  health: any;
  metrics: any;
  tasks: BackendTask[];
  robots: BackendRobot[];
  warehouse: WarehouseNode[];
  allocations: CBAAAllocation[];
  deadlocks: DeadlockState;
  conflicts: ConflictRecord[];
  reservations: SpaceTimeReservation[];
  paths: BackendPath[];
  congestion: any[];
  obstacles: any[];
  failures: any[];
  aiStatus: any;
  aiMetrics: any;
  aiFeatures: any;
  benchmark?: BenchmarkResult;
  gazeboStatus?: GazeboStatus;
  config?: any;
  peerStatus?: any;
  peerMessages?: any[];
};

export type SimulationState = {
  simulation: string;
  status: string;
  racks: number;
  rf_nodes: number;
  slam_scans: number;
  route_distance_m: number;
  travel_time_s: number;
  robots: Array<{
    robot_id: string;
    status: string;
    node_id: string;
    battery: number;
    health: number;
  }>;
  task: {
    task_id: string;
    pickup: string;
    destination: string;
    original_robot: string;
    recovery_robot: string;
    status: string;
  };
  route: string[];
  cbaa: {
    winner: string;
    weights: { distance: number; travel_time: number; congestion: number; availability: number };
    bids: Record<string, { cost: number; status: string }>;
  };
  events: any[];
};

export type SimulationWarehouse = {
  total_rf_nodes: number;
  total_racks: number;
  rf_nodes: Array<{
    node_id: string;
    x: number;
    y: number;
    type: string;
    neighbors: string[];
  }>;
  racks: Array<{
    rack_id: string;
    x: number;
    y: number;
    width: number;
    depth: number;
  }>;
  grid_spacing_m: number;
  grid_rows: number;
  grid_cols: number;
  x_start: number;
  y_start: number;
};
