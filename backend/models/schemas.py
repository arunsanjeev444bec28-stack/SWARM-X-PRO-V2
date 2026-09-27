from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class Node(BaseModel):
    node_id: str
    x: float
    y: float
    type: str
    neighbors: List[str]
    health: float = 100.0

class Obstacle(BaseModel):
    node_id: str
    duration: int

class FailureRequest(BaseModel):
    robot_id: str

class Rack(BaseModel):
    rack_id: str
    x: float
    y: float
    width: float
    height: float

class NavEdge(BaseModel):
    from_node: str
    to_node: str
    distance: float
    blocked: bool = False

class WarehouseModel(BaseModel):
    racks: List[Rack]
    aisles: List[Dict[str, Any]] = []
    intersections: List[Dict[str, Any]] = []
    rf_nodes: Dict[str, Node]
    edges: List[NavEdge]
    dimensions: Dict[str, float]
    corner_nodes: Dict[str, str]

class Task(BaseModel):
    task_id: str
    pickup_node: str
    dispatch_node: str
    priority: str = "NORMAL"
    urgency: float = 1.0
    deadline: float = 120.0
    load: float = 1.0
    energy_requirement: float = 10.0
    task_type: Optional[str] = "TRANSPORT"
    status: Optional[str] = "PENDING"
    winner: Optional[str] = None

class Robot(BaseModel):
    robot_id: str
    node_id: str
    battery: float = 100.0
    temperature: float = 25.0
    load: float = 0.0
    health: float = 100.0
    status: str = "AVAILABLE"
    position: Optional[List[float]] = None

# API Response Models
class AllocationResponse(BaseModel):
    task_id: str
    winner: Optional[str]
    winning_bid: Optional[float] = None
    selection_rule: Optional[str] = "MINIMUM VALID BID"
    feasible_robots: List[str]
    bids: Dict[str, Any]
    reason: str
    ineligible_robots: Dict[str, str] = {}

class TrajectoryStep(BaseModel):
    node_id: str
    time_step: int

class PlanningResponse(BaseModel):
    robot_id: str
    task_id: str
    path: List[str]
    trajectory: List[TrajectoryStep]
    distance: float
    estimated_time: float
    replanned: bool
    conflict_with: Optional[str] = None
    conflict_node: Optional[str] = None
    conflict_time_step: Optional[int] = None
    unconstrained_path: Optional[List[str]] = None
    blocking_robots: Optional[List[str]] = None

class ConflictResponse(BaseModel):
    conflict_id: str
    robot_1: str
    robot_2: str
    type: str  # "VERTEX" | "EDGE_SWAP"
    time_step: int
    resolved: bool
    resolution: str

# AllocationResult model for internal state tracking (alias of AllocationResponse)
class AllocationResult(AllocationResponse):
    """Alias for AllocationResponse used by GlobalState.allocations.
    Inherits all fields from AllocationResponse.
    """
    pass
