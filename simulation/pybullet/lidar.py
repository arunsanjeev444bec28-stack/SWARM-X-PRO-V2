"""
Simulated 2D LiDAR Sensor for PyBullet.
Performs real 360-degree ray casting against simulated warehouse geometry
(78 racks, boundary walls, other AMRs, dynamic obstacles).
No fake/random points — measurements originate from actual physical meshes.
Includes rich diagnostic mode, self-hit filtering, and corridor-based obstacle assessment.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Optional, Tuple
import pybullet as p

from backend.data.warehouse_real import (
    generate_78_racks,
    generate_rf_nodes,
    ROBOT_WIDTH,
)

logger = logging.getLogger("simulation.lidar")

# Cache static reference geometry for distance lookups
_STATIC_RACKS = generate_78_racks()
_STATIC_NODES = list(generate_rf_nodes().values())


class SimulatedLiDAR:
    """Simulates a 2D planar LiDAR sensor via PyBullet rayTestBatch."""

    def __init__(
        self,
        robot_id: str,
        client_id: int,
        num_rays: int = 180,           # 180 rays = 2-degree resolution (fast & high fidelity)
        max_range: float = 10.0,        # 10 meters maximum sensing distance
        min_range: float = 0.20,        # 0.20 meters minimum range
        sensor_height: float = 0.28,    # Mounted on top of AMR chassis
        fov_degrees: float = 360.0,    # Full 360-degree field of view
        update_hz: float = 10.0,        # Default 10 Hz
    ):
        self.robot_id = robot_id
        self.client_id = client_id
        self.num_rays = num_rays
        self.max_range = max_range
        self.min_range = min_range
        self.sensor_height = sensor_height
        self.fov_rad = math.radians(fov_degrees)
        self.update_hz = update_hz

        # Precompute relative angles [-pi to +pi)
        step = self.fov_rad / self.num_rays
        start_angle = -self.fov_rad / 2.0
        self.ray_angles = [start_angle + i * step for i in range(self.num_rays)]

        self.last_scan: Optional[Dict[str, Any]] = None
        self.total_scans: int = 0

    def scan(
        self,
        robot_x: float,
        robot_y: float,
        robot_yaw: float,
        robot_body_id: int = -1,
        body_lookup: Optional[Dict[int, Dict[str, Any]]] = None,
        active_obstacles: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Execute 360-degree batch ray-casting against PyBullet world geometry.
        Returns range measurements, world-space hit points, obstacle flags,
        and full diagnostics per Section 6 and 7.
        """
        ray_from_positions: List[List[float]] = []
        ray_to_positions: List[List[float]] = []
        z = self.sensor_height

        for angle in self.ray_angles:
            global_angle = robot_yaw + angle
            rx_end = robot_x + self.max_range * math.cos(global_angle)
            ry_end = robot_y + self.max_range * math.sin(global_angle)

            # Start ray at minimum range to prevent self-collision
            rx_start = robot_x + self.min_range * math.cos(global_angle)
            ry_start = robot_y + self.min_range * math.sin(global_angle)

            ray_from_positions.append([rx_start, ry_start, z])
            ray_to_positions.append([rx_end, ry_end, z])

        # Execute PyBullet ray cast
        results = p.rayTestBatch(
            rayFromPositions=ray_from_positions,
            rayToPositions=ray_to_positions,
            physicsClientId=self.client_id,
        )

        ranges: List[float] = []
        hit_points: List[List[float]] = []
        forward_obstacle: Optional[Dict[str, Any]] = None
        min_dist = self.max_range
        nearest_hit_info: Optional[Dict[str, Any]] = None
        hit_count = 0

        # Corridor half-width: robot width is 0.40m (half-width 0.20m)
        # Adding 0.06m margin gives a travel lane corridor of 0.26m on each side.
        # Side racks at aisle boundary are at lateral distance >= 0.50m and will NOT trigger false blockage.
        corridor_half_width = (ROBOT_WIDTH / 2.0) + 0.06

        for i, res in enumerate(results):
            hit_object_uid = res[0]
            hit_fraction = res[2]
            hit_position = res[3]
            angle = self.ray_angles[i]

            # 1. Filter out self-hits and invalid hits
            if hit_object_uid == robot_body_id or hit_object_uid < 0:
                dist = self.max_range
                ranges.append(dist)
                continue

            if hit_fraction < 1.0:
                dist = round(self.min_range + hit_fraction * (self.max_range - self.min_range), 3)
                ranges.append(dist)
                hit_px = round(hit_position[0], 3)
                hit_py = round(hit_position[1], 3)
                hit_points.append([hit_px, hit_py])
                hit_count += 1

                # Resolve object identity
                obj_info = (body_lookup.get(hit_object_uid) if body_lookup else None) or {}
                obj_id = obj_info.get("id", f"BODY_{hit_object_uid}")
                obj_type = obj_info.get("type", "UNKNOWN")

                if dist < min_dist:
                    min_dist = dist
                    nearest_hit_info = {
                        "object_id": obj_id,
                        "object_type": obj_type,
                        "position": [hit_px, hit_py],
                        "distance": dist,
                        "ray_index": i,
                        "angle_deg": round(math.degrees(angle), 1),
                    }

                # 2. Corridor-based forward obstacle check:
                # Along robot heading: x_local = dist * cos(angle)
                # Lateral offset: y_local = dist * sin(angle)
                x_local = dist * math.cos(angle)
                y_local = dist * math.sin(angle)

                # Obstacle is in forward movement corridor within stop threshold (0.20m to 1.30m)
                if (0.20 < x_local < 1.30) and (abs(y_local) <= corridor_half_width):
                    if forward_obstacle is None or dist < forward_obstacle["distance"]:
                        forward_obstacle = {
                            "robot_id": self.robot_id,
                            "robot_position": [round(robot_x, 3), round(robot_y, 3)],
                            "robot_heading": round(robot_yaw, 3),
                            "detected_object_id": obj_id,
                            "detected_object_type": obj_type,
                            "detected_object_position": [hit_px, hit_py],
                            "measured_distance": dist,
                            "distance": dist,
                            "ray_index": i,
                            "lidar_angle_deg": round(math.degrees(angle), 1),
                            "point": [hit_px, hit_py],
                            "body_id": hit_object_uid,
                        }
            else:
                ranges.append(self.max_range)

        self.total_scans += 1

        # Nearest reference calculations for diagnostics
        nearest_rack_obj = min(_STATIC_RACKS, key=lambda r: math.hypot(r.x - robot_x, r.y - robot_y))
        dist_to_rack = round(math.hypot(nearest_rack_obj.x - robot_x, nearest_rack_obj.y - robot_y), 3)

        nearest_node_obj = min(_STATIC_NODES, key=lambda n: math.hypot(n.x - robot_x, n.y - robot_y))
        dist_to_node = round(math.hypot(nearest_node_obj.x - robot_x, nearest_node_obj.y - robot_y), 3)

        nearest_obstacle_id = "NONE"
        nearest_obstacle_dist = 999.0
        if active_obstacles:
            for obs_id, (ox, oy) in active_obstacles.items():
                od = math.hypot(ox - robot_x, oy - robot_y)
                if od < nearest_obstacle_dist:
                    nearest_obstacle_dist = od
                    nearest_obstacle_id = obs_id

        nearest_obj_label = nearest_hit_info["object_id"] if nearest_hit_info else "NONE"

        # Diagnostic summary text
        diag_summary = (
            f"LIDAR STATUS: ONLINE | RAYS: {self.num_rays} | HITS: {hit_count} | "
            f"NEAREST HIT: {min_dist:.2f}m | NEAREST OBJECT: {nearest_obj_label} | "
            f"MAX RANGE: {self.max_range:.1f}m | UPDATE RATE: {self.update_hz:.0f} Hz"
        )

        scan_data = {
            "robot_id": self.robot_id,
            "timestamp": time.time(),
            "scan_index": self.total_scans,
            "pose": {
                "x": round(robot_x, 3),
                "y": round(robot_y, 3),
                "yaw": round(robot_yaw, 3),
            },
            "num_rays": self.num_rays,
            "min_range": self.min_range,
            "max_range": self.max_range,
            "ranges": ranges,
            "points": hit_points,
            "min_distance": round(min_dist, 3),
            "obstacle_detected": (forward_obstacle is not None),
            "forward_obstacle": forward_obstacle,
            "diagnostics": {
                "robot_id": self.robot_id,
                "robot_position": [round(robot_x, 3), round(robot_y, 3)],
                "robot_heading": round(robot_yaw, 3),
                "nearest_rack": {"rack_id": nearest_rack_obj.rack_id, "distance": dist_to_rack},
                "nearest_rf_node": {"node_id": nearest_node_obj.node_id, "distance": dist_to_node},
                "nearest_obstacle": {
                    "obstacle_id": nearest_obstacle_id,
                    "distance": round(nearest_obstacle_dist, 3) if nearest_obstacle_dist < 900 else None,
                },
                "nearest_hit": nearest_hit_info,
                "rays": self.num_rays,
                "hits": hit_count,
                "min_distance": round(min_dist, 3),
                "update_rate_hz": self.update_hz,
                "summary": diag_summary,
            },
            "diagnostic_text": diag_summary,
        }

        # If forward obstacle detected, append nearest rack/node context
        if forward_obstacle:
            forward_obstacle["nearest_rack"] = nearest_rack_obj.rack_id
            forward_obstacle["nearest_rf_node"] = nearest_node_obj.node_id
            forward_obstacle["nearest_obstacle"] = nearest_obstacle_id

        self.last_scan = scan_data
        return scan_data

    def get_diagnostics(self) -> Dict[str, Any]:
        """Return diagnostic metrics of the LiDAR sensor."""
        if self.last_scan:
            diag = dict(self.last_scan.get("diagnostics", {}))
            diag["status"] = "OPERATIONAL"
            diag["obstacle_detected"] = self.last_scan.get("obstacle_detected", False)
            diag["max_range_m"] = self.max_range
            diag["nearest_hit_m"] = self.last_scan.get("min_distance", self.max_range)
            return diag
        return {
            "status": "OPERATIONAL",
            "rays": self.num_rays,
            "max_range_m": self.max_range,
            "obstacle_detected": False,
            "nearest_hit_m": self.max_range,
        }
