"""
LiDAR Scan Processing and Coordinate Transforms for 2D SLAM.
Transforms polar sensor measurements into world-frame ray segments for occupancy updating.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from .pose import RobotPose


class ScanProcessor:
    """Processes raw LiDAR scans and projects rays into world coordinates."""

    def __init__(self, max_range: float = 10.0):
        self.max_range = max_range

    def process_scan(
        self,
        pose: RobotPose,
        scan_data: Dict[str, Any],
    ) -> List[Tuple[float, float, float, float, bool]]:
        """
        Transform raw scan ranges into world-frame ray segments:
        Returns list of (start_x, start_y, end_x, end_y, is_hit).
        """
        ranges: List[float] = scan_data.get("ranges", [])
        num_rays = len(ranges)
        if num_rays == 0:
            return []

        fov_rad = 2.0 * math.pi
        step = fov_rad / num_rays
        start_angle = -math.pi

        ray_segments: List[Tuple[float, float, float, float, bool]] = []
        x0, y0 = pose.x, pose.y

        for i, r in enumerate(ranges):
            local_angle = start_angle + i * step
            global_angle = pose.yaw + local_angle

            # Clamp valid range
            dist = max(0.20, min(r, self.max_range))
            is_hit = (r < self.max_range - 0.05)

            x1 = x0 + dist * math.cos(global_angle)
            y1 = y0 + dist * math.sin(global_angle)

            ray_segments.append((x0, y0, x1, y1, is_hit))

        return ray_segments
