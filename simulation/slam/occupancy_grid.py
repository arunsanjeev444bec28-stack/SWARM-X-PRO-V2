"""
2D Occupancy Grid Map Implementation for Real-Time SLAM.
Uses Bresenham ray marching to carve free space and mark geometric obstacle boundaries.
Cells:
  -1 : UNKNOWN (unexplored)
   0 : FREE (traversed by LiDAR ray)
 100 : OCCUPIED (surface hit detected)
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


class OccupancyGrid:
    """Manages 2D probabilistic/discrete occupancy grid for warehouse mapping."""

    def __init__(
        self,
        min_x: float = -17.5,
        max_x: float = 17.5,
        min_y: float = -7.5,
        max_y: float = 7.5,
        resolution: float = 0.10,  # 10 cm per grid cell
    ):
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.resolution = resolution

        self.width_m = max_x - min_x
        self.height_m = max_y - min_y
        self.cols = int(round(self.width_m / resolution))
        self.rows = int(round(self.height_m / resolution))

        # Grid cells: -1 = unknown, 0 = free, 100 = occupied
        self.grid = np.full((self.rows, self.cols), -1, dtype=np.int8)

        # Hit count / observation counter for robust filtering
        self.hits = np.zeros((self.rows, self.cols), dtype=np.uint16)
        self.passes = np.zeros((self.rows, self.cols), dtype=np.uint16)

        self.total_cells = self.rows * self.cols
        self.scan_count = 0

    def world_to_grid(self, x: float, y: float) -> Optional[Tuple[int, int]]:
        """Convert world coordinates (x, y) in meters to grid cell (col, row)."""
        if x < self.min_x or x >= self.max_x or y < self.min_y or y >= self.max_y:
            return None
        c = int((x - self.min_x) / self.resolution)
        r = int((y - self.min_y) / self.resolution)
        c = min(max(c, 0), self.cols - 1)
        r = min(max(r, 0), self.rows - 1)
        return (c, r)

    def grid_to_world(self, col: int, row: int) -> Tuple[float, float]:
        """Convert grid cell (col, row) to center world coordinates (x, y) in meters."""
        x = round(self.min_x + (col + 0.5) * self.resolution, 3)
        y = round(self.min_y + (row + 0.5) * self.resolution, 3)
        return (x, y)

    def bresenham_line(self, c0: int, r0: int, c1: int, r1: int) -> List[Tuple[int, int]]:
        """Compute grid cells along a 2D line segment using Bresenham's algorithm."""
        cells: List[Tuple[int, int]] = []
        dc = abs(c1 - c0)
        dr = abs(r1 - r0)
        sc = 1 if c0 < c1 else -1
        sr = 1 if r0 < r1 else -1
        err = dc - dr

        curr_c, curr_r = c0, r0
        while True:
            cells.append((curr_c, curr_r))
            if curr_c == c1 and curr_r == r1:
                break
            e2 = 2 * err
            if e2 > -dr:
                err -= dr
                curr_c += sc
            if e2 < dc:
                err += dc
                curr_r += sr
        return cells

    def update_ray(self, x0: float, y0: float, x1: float, y1: float, is_hit: bool) -> None:
        """Update occupancy grid for a single LiDAR ray."""
        p0 = self.world_to_grid(x0, y0)
        p1 = self.world_to_grid(x1, y1)

        if not p0 or not p1:
            return

        c0, r0 = p0
        c1, r1 = p1

        cells = self.bresenham_line(c0, r0, c1, r1)
        if not cells:
            return

        # Intermediate cells are free space
        free_cells = cells[:-1] if is_hit else cells
        for c, r in free_cells:
            self.passes[r, c] = min(65535, self.passes[r, c] + 1)
            # Only mark free if not already strongly occupied
            if self.grid[r, c] != 100:
                self.grid[r, c] = 0

        # Endpoint is occupied if hit
        if is_hit:
            self.hits[r1, c1] = min(65535, self.hits[r1, c1] + 1)
            self.grid[r1, c1] = 100

    def update_batch(self, rays: List[Tuple[float, float, float, float, bool]]) -> None:
        """Process a full 360-degree LiDAR scan."""
        for x0, y0, x1, y1, is_hit in rays:
            self.update_ray(x0, y0, x1, y1, is_hit)
        self.scan_count += 1

    def get_coverage_percent(self) -> float:
        """Compute explored map coverage as a percentage of warehouse grid."""
        known = int(np.count_nonzero(self.grid != -1))
        return round(100.0 * known / float(self.total_cells), 2)

    def get_occupied_points(self, max_points: int = 2000) -> List[List[float]]:
        """Return world coordinates [[x, y], ...] of occupied cells."""
        occ_indices = np.argwhere(self.grid == 100)
        if len(occ_indices) > max_points:
            # Subsample evenly
            step = len(occ_indices) // max_points
            occ_indices = occ_indices[::step]

        points: List[List[float]] = []
        for r, c in occ_indices:
            wx, wy = self.grid_to_world(int(c), int(r))
            points.append([wx, wy])
        return points

    def get_compact_grid(self, scale_down: int = 2) -> Dict[str, Any]:
        """
        Return downsampled or run-length representation for efficient WebSocket transmission.
        scale_down=2 downsamples 350x150 to 175x75 cells (13,125 bytes).
        """
        if scale_down > 1:
            down_rows = self.rows // scale_down
            down_cols = self.cols // scale_down
            sub = self.grid[:down_rows * scale_down, :down_cols * scale_down]
            # Max pooling to preserve occupied cells (100 > 0 > -1)
            reshaped = sub.reshape(down_rows, scale_down, down_cols, scale_down)
            downsampled = reshaped.max(axis=(1, 3))
            raw_cells = downsampled.flatten().tolist()
            res = self.resolution * scale_down
            cols = down_cols
            rows = down_rows
        else:
            raw_cells = self.grid.flatten().tolist()
            res = self.resolution
            cols = self.cols
            rows = self.rows

        return {
            "cols": cols,
            "rows": rows,
            "resolution": round(res, 3),
            "origin_x": self.min_x,
            "origin_y": self.min_y,
            "cells": raw_cells,  # Flat list of -1 (unknown), 0 (free), 100 (occupied)
        }

    def reset(self) -> None:
        """Reset map to completely unexplored state."""
        self.grid.fill(-1)
        self.hits.fill(0)
        self.passes.fill(0)
        self.scan_count = 0
