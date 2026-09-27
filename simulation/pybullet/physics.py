"""
Physics Engine Stepping and Clock Synchronization for PyBullet.
"""

from __future__ import annotations

import logging
import time
from typing import Optional
import pybullet as p

logger = logging.getLogger("simulation.physics")


class PhysicsEngine:
    """Controls the PyBullet physics execution loop and timing."""

    def __init__(self, client_id: int, target_hz: float = 60.0):
        self.client_id = client_id
        self.target_hz = target_hz
        self.dt = 1.0 / target_hz
        self.last_step_time = time.time()
        self.simulation_step_count = 0

    def step(self) -> float:
        """Advance one physics step."""
        now = time.time()
        elapsed = now - self.last_step_time
        self.last_step_time = now

        p.stepSimulation(physicsClientId=self.client_id)
        self.simulation_step_count += 1
        return min(elapsed, 0.1)

    def reset(self) -> None:
        """Reset step count and clock."""
        self.last_step_time = time.time()
        self.simulation_step_count = 0
