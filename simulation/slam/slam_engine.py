"""
SLAM Engine for SWARM-X PRO V2.
Coordinates 2D occupancy mapping, pose estimation, trajectory logging,
and live dashboard synchronization for each AMR.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional
from .pose import RobotPose, PoseTracker
from .scan_processor import ScanProcessor
from .occupancy_grid import OccupancyGrid

logger = logging.getLogger("simulation.slam")


class SlamEngine:
    """Manages real-time 2D occupancy-grid SLAM for fleet AMRs."""

    def __init__(self, resolution: float = 0.10):
        self.resolution = resolution
        self.is_running = True
        self.active_robot_id = "R1"

        # Separate mapping instances per AMR
        self.grids: Dict[str, OccupancyGrid] = {}
        self.pose_trackers: Dict[str, PoseTracker] = {}
        self.processors: Dict[str, ScanProcessor] = {}
        self.latest_scans: Dict[str, Dict[str, Any]] = {}

        for rid in ["R1", "R2", "R3", "R4"]:
            self.grids[rid] = OccupancyGrid(resolution=self.resolution)
            self.pose_trackers[rid] = PoseTracker()
            self.processors[rid] = ScanProcessor(max_range=10.0)

    def set_active_robot(self, robot_id: str) -> bool:
        """Switch active SLAM view to specified robot."""
        if robot_id in self.grids:
            self.active_robot_id = robot_id
            return True
        return False

    def start(self) -> None:
        """Resume SLAM updates."""
        self.is_running = True
        logger.info("SLAM engine started/resumed")

    def pause(self) -> None:
        """Pause SLAM map updates."""
        self.is_running = False
        logger.info("SLAM engine paused")

    def reset_map(self, robot_id: Optional[str] = None) -> None:
        """Reset occupancy grid to empty/unknown."""
        target_ids = [robot_id] if robot_id else list(self.grids.keys())
        for rid in target_ids:
            if rid in self.grids:
                self.grids[rid].reset()
        logger.info("Reset SLAM map for %s", target_ids)

    def clear_trajectory(self, robot_id: Optional[str] = None) -> None:
        """Clear trajectory history."""
        target_ids = [robot_id] if robot_id else list(self.pose_trackers.keys())
        for rid in target_ids:
            if rid in self.pose_trackers:
                self.pose_trackers[rid].clear_trajectory()
        logger.info("Cleared SLAM trajectory for %s", target_ids)

    def process_scan(
        self,
        robot_id: str,
        pose_data: Dict[str, Any],
        scan_data: Dict[str, Any],
    ) -> None:
        """
        Process a live LiDAR scan observation from PyBullet.
        Updates robot pose, converts rays to world coordinates, and updates occupancy grid.
        """
        if not self.is_running:
            return

        if robot_id not in self.grids:
            self.grids[robot_id] = OccupancyGrid(resolution=self.resolution)
            self.pose_trackers[robot_id] = PoseTracker()
            self.processors[robot_id] = ScanProcessor(max_range=10.0)

        # 1. Update pose
        rx = float(pose_data.get("x", 0.0))
        ry = float(pose_data.get("y", 0.0))
        ryaw = float(pose_data.get("yaw", 0.0))
        current_pose = self.pose_trackers[robot_id].update(rx, ry, ryaw)

        # 2. Process rays
        processor = self.processors[robot_id]
        ray_segments = processor.process_scan(current_pose, scan_data)

        # 3. Update occupancy grid
        self.grids[robot_id].update_batch(ray_segments)
        self.latest_scans[robot_id] = scan_data

    def get_slam_state(
        self,
        robot_id: Optional[str] = None,
        include_grid: bool = True,
        scale_down: int = 2,
    ) -> Dict[str, Any]:
        """
        Return structured SLAM state for the active or requested robot,
        or combined multi-robot SLAM when robot_id == 'ALL'.
        """
        rid = (robot_id or self.active_robot_id).upper()

        if rid == "ALL":
            # Combined multi-robot SLAM
            combined_grid = OccupancyGrid(resolution=self.resolution)
            for g in self.grids.values():
                occ_mask = g.grid >= 100
                free_mask = (g.grid == 0) & (combined_grid.grid < 100)
                combined_grid.grid[occ_mask] = 100
                combined_grid.grid[free_mask] = 0
                combined_grid.scan_count += g.scan_count

            all_poses = {r: self.pose_trackers[r].current_pose.to_dict() for r in self.grids}
            all_trajectories = {r: self.pose_trackers[r].get_trajectory_points()[-150:] for r in self.grids}
            all_lidar_points: List[List[float]] = []
            for sc in self.latest_scans.values():
                all_lidar_points.extend(sc.get("points", []))

            result: Dict[str, Any] = {
                "status": "RUNNING" if self.is_running else "PAUSED",
                "robot_id": "ALL",
                "scan_count": combined_grid.scan_count,
                "coverage_percent": combined_grid.get_coverage_percent(),
                "map_resolution": combined_grid.resolution,
                "pose": self.pose_trackers["R1"].current_pose.to_dict(),
                "all_poses": all_poses,
                "trajectory": self.pose_trackers["R1"].get_trajectory_points()[-150:],
                "all_trajectories": all_trajectories,
                "lidar_points": all_lidar_points[:2000],
                "forward_obstacle": None,
                "distance_traveled": round(sum(pt.distance_traveled for pt in self.pose_trackers.values()), 2),
                "dimensions": {
                    "min_x": combined_grid.min_x,
                    "max_x": combined_grid.max_x,
                    "min_y": combined_grid.min_y,
                    "max_y": combined_grid.max_y,
                    "width_m": combined_grid.width_m,
                    "height_m": combined_grid.height_m,
                    "cols": combined_grid.cols,
                    "rows": combined_grid.rows,
                },
            }
            if include_grid:
                result["occupancy_grid"] = combined_grid.get_compact_grid(scale_down=scale_down)
                result["occupied_points"] = combined_grid.get_occupied_points(max_points=2000)
            return result

        if rid not in self.grids:
            rid = "R1"

        grid = self.grids[rid]
        pose_tracker = self.pose_trackers[rid]
        latest_scan = self.latest_scans.get(rid, {})

        status_str = "RUNNING" if self.is_running else "PAUSED"
        coverage = grid.get_coverage_percent()
        trajectory = pose_tracker.get_trajectory_points()
        lidar_points = latest_scan.get("points", [])
        forward_obstacle = latest_scan.get("forward_obstacle")

        result = {
            "status": status_str,
            "robot_id": rid,
            "scan_count": grid.scan_count,
            "coverage_percent": coverage,
            "map_resolution": grid.resolution,
            "pose": pose_tracker.current_pose.to_dict(),
            "trajectory": trajectory[-150:],  # Recent 150 path waypoints
            "lidar_points": lidar_points,
            "forward_obstacle": forward_obstacle,
            "distance_traveled": round(pose_tracker.distance_traveled, 2),
            "dimensions": {
                "min_x": grid.min_x,
                "max_x": grid.max_x,
                "min_y": grid.min_y,
                "max_y": grid.max_y,
                "width_m": grid.width_m,
                "height_m": grid.height_m,
                "cols": grid.cols,
                "rows": grid.rows,
            },
        }

        if include_grid:
            result["occupancy_grid"] = grid.get_compact_grid(scale_down=scale_down)
            result["occupied_points"] = grid.get_occupied_points(max_points=1200)

        return result

