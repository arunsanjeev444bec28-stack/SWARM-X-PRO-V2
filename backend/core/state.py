from typing import Dict, List, Optional
from models.schemas import Node, Robot, Task

class StateManager:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.robots: Dict[str, Robot] = {}
        self.tasks: Dict[str, Task] = {}
        # Simple tracking of what task is assigned to what robot
        self.robot_tasks: Dict[str, str] = {}
        # Track active paths: robot_id -> List[TrajectoryStep]
        self.robot_paths: Dict[str, List] = {}
        # Maps for phase 2
        self.robot_charging_timers: Dict[str, int] = {}
        self.dynamic_obstacles: Dict[str, int] = {}
        self.congestion_map: Dict[str, float] = {}
        # Evidence projections populated by the existing API/algorithm flows.
        self.allocations: List[dict] = []
        self.conflicts: List[dict] = []
        self.failures: List[dict] = []
        self.events: List[dict] = []
        self.last_benchmark: Optional[dict] = None
        self.peer_messages: List[dict] = []
        self.path_records: List[dict] = []
        self.reservation_records: List[dict] = []
    
    def reset(self):
        self.nodes.clear()
        self.robots.clear()
        self.tasks.clear()
        self.robot_tasks.clear()
        self.robot_paths.clear()
        self.robot_charging_timers.clear()
        self.dynamic_obstacles.clear()
        self.congestion_map.clear()
        self.allocations.clear()
        self.conflicts.clear()
        self.failures.clear()
        self.events.clear()
        self.last_benchmark = None
        self.peer_messages.clear()
        self.path_records.clear()
        self.reservation_records.clear()

    def add_node(self, node: Node):
        self.nodes[node.node_id] = node

    def add_robot(self, robot: Robot):
        self.robots[robot.robot_id] = robot

    def add_task(self, task: Task):
        self.tasks[task.task_id] = task

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def get_robot(self, robot_id: str) -> Optional[Robot]:
        return self.robots.get(robot_id)

    def get_task(self, task_id: str) -> Optional[Task]:
        return self.tasks.get(task_id)

    def get_all_nodes(self) -> List[Node]:
        return list(self.nodes.values())

    def get_all_robots(self) -> List[Robot]:
        return list(self.robots.values())

    def get_all_tasks(self) -> List[Task]:
        return list(self.tasks.values())

# Global state instance
global_state = StateManager()

import sys
current_mod = sys.modules.get(__name__)
if current_mod is not None:
    sys.modules["core.state"] = current_mod
    sys.modules["backend.core.state"] = current_mod

