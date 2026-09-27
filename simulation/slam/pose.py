"""
Robot Pose and Trajectory Tracking for 2D SLAM.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple


@dataclass
class RobotPose:
    """Represents planar AMR pose."""
    x: float
    y: float
    yaw: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "yaw": round(self.yaw, 3),
            "timestamp": self.timestamp,
        }


class PoseTracker:
    """Maintains continuous pose estimates and trajectory history."""

    def __init__(self, initial_pose: Optional[RobotPose] = None):
        self.current_pose = initial_pose or RobotPose(0.0, 0.0, 0.0)
        self.trajectory: List[Tuple[float, float, float]] = []  # (x, y, timestamp)
        self.distance_traveled: float = 0.0
        if initial_pose:
            self.trajectory.append((initial_pose.x, initial_pose.y, initial_pose.timestamp))

    def update(self, x: float, y: float, yaw: float) -> RobotPose:
        """Update current pose and record trajectory waypoint."""
        now = time.time()
        dx = x - self.current_pose.x
        dy = y - self.current_pose.y
        dist = math.hypot(dx, dy)

        if dist > 0.001:
            self.distance_traveled += dist

        self.current_pose = RobotPose(x=x, y=y, yaw=yaw, timestamp=now)

        # Append to trajectory if moved > 10cm or empty
        if not self.trajectory or dist > 0.10:
            self.trajectory.append((round(x, 3), round(y, 3), now))

        return self.current_pose

    def clear_trajectory(self) -> None:
        """Clear recorded trajectory path."""
        self.trajectory = [(self.current_pose.x, self.current_pose.y, time.time())]
        self.distance_traveled = 0.0

    def get_trajectory_points(self) -> List[List[float]]:
        """Return list of [x, y] coordinates for path visualization."""
        return [[p[0], p[1]] for p in self.trajectory]
