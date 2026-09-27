from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RobotState:
    """Strongly typed robot-local state for edge agents.

    This intentionally mirrors the key fields needed for distributed local
    decision-making without duplicating the full backend schema.
    """

    robot_id: str
    timestamp: float
    x: float
    y: float
    heading: float = 0.0
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    battery: float = 100.0
    status: str = "IDLE"
    current_task_id: Optional[str] = None
    target_node: Optional[str] = None
    current_node: Optional[str] = None
    planned_path: List[str] = field(default_factory=list)
    current_path_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "timestamp": self.timestamp,
            "x": self.x,
            "y": self.y,
            "heading": self.heading,
            "linear_velocity": self.linear_velocity,
            "angular_velocity": self.angular_velocity,
            "battery": self.battery,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "target_node": self.target_node,
            "current_node": self.current_node,
            "planned_path": list(self.planned_path),
            "current_path_index": self.current_path_index,
        }


@dataclass
class NeighborState:
    robot_id: str
    last_seen: float
    status: str = "UNKNOWN"
    battery: Optional[float] = None
    current_task_id: Optional[str] = None
    target_node: Optional[str] = None
    current_node: Optional[str] = None
    distance_m: Optional[float] = None
    heartbeat_seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "last_seen": self.last_seen,
            "status": self.status,
            "battery": self.battery,
            "current_task_id": self.current_task_id,
            "target_node": self.target_node,
            "current_node": self.current_node,
            "distance_m": self.distance_m,
            "heartbeat_seq": self.heartbeat_seq,
        }
