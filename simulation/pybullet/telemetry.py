"""
Simulation Telemetry Collector for SWARM-X PRO V2.
Formats real-time continuous robot poses, LiDAR diagnostics, and fleet status
for WebSocket broadcasting to the React dashboard.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from simulation.pybullet.robot import AMRRobot


class TelemetryCollector:
    """Collects and formats live AMR telemetry for frontend synchronization."""

    def __init__(self, robots: Dict[str, AMRRobot]):
        self.robots = robots
        self.start_time = time.time()
        self.step_count = 0

    def get_robot_telemetry(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Return standardized telemetry packet for a single AMR."""
        robot = self.robots.get(robot_id)
        if not robot:
            return None

        return {
            "robot_id": robot.robot_id,
            "x": round(robot.x, 3),
            "y": round(robot.y, 3),
            "z": round(robot.z, 3),
            "yaw": round(robot.yaw, 3),
            "speed": round(robot.speed, 2),
            "current_node": robot.current_node,
            "next_node": robot.next_node,
            "target_node": robot.target_node,
            "status": robot.status,
            "battery": round(robot.battery, 1),
            "task_id": robot.task_id,
            "route": list(robot.route),
            "lidar_status": "ONLINE" if not robot.is_failed else "OFFLINE",
            "slam_status": "ACTIVE" if robot.speed > 0 else "STANDBY",
            "is_waiting": robot.is_waiting,
            "is_failed": robot.is_failed,
            "trajectory_points": len(robot.trajectory_history),
        }

    def get_fleet_telemetry(self) -> Dict[str, Any]:
        """Return aggregated fleet telemetry packet."""
        robots_data = [self.get_robot_telemetry(rid) for rid in sorted(self.robots.keys())]
        now = time.time()
        uptime = round(now - self.start_time, 1)

        moving_count = sum(1 for r in self.robots.values() if r.speed > 0.05)
        available_count = sum(1 for r in self.robots.values() if r.status in ["AVAILABLE", "IDLE"])
        failed_count = sum(1 for r in self.robots.values() if r.is_failed)
        waiting_count = sum(1 for r in self.robots.values() if r.is_waiting)

        return {
            "timestamp": now,
            "uptime_seconds": uptime,
            "step_count": self.step_count,
            "fleet_summary": {
                "total": len(self.robots),
                "available": available_count,
                "moving": moving_count,
                "waiting": waiting_count,
                "failed": failed_count,
            },
            "robots": robots_data,
        }
