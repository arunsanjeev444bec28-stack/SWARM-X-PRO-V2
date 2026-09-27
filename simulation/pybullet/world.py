"""
PyBullet Simulation World Management for SWARM-X PRO V2.
Handles physics client connection, GUI/DIRECT fallback, camera setup, and stepping.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple
import pybullet as p

logger = logging.getLogger("simulation.world")


class SimulationWorld:
    """Manages the PyBullet physics client, gravity, timestep, and visualizer."""

    def __init__(self, gui: bool = True, time_step: float = 1.0 / 60.0):
        self.requested_gui = gui
        self.is_gui = False
        self.client_id = -1
        self.time_step = time_step
        self.is_connected = False
        self._init_physics()

    def _init_physics(self) -> None:
        """Connect to PyBullet in GUI or DIRECT mode."""
        if self.requested_gui:
            try:
                # Attempt GUI connection
                self.client_id = p.connect(p.GUI)
                if self.client_id >= 0:
                    self.is_gui = True
                    logger.info("Connected to PyBullet GUI visualizer (client %d)", self.client_id)
                else:
                    logger.warning("Failed to open PyBullet GUI, falling back to DIRECT mode")
                    self.client_id = p.connect(p.DIRECT)
                    self.is_gui = False
            except Exception as e:
                logger.warning("Exception opening PyBullet GUI: %s. Falling back to DIRECT mode", e)
                self.client_id = p.connect(p.DIRECT)
                self.is_gui = False
        else:
            self.client_id = p.connect(p.DIRECT)
            self.is_gui = False
            logger.info("Connected to PyBullet DIRECT mode (client %d)", self.client_id)

        self.is_connected = (self.client_id >= 0)

        # Physics setup
        p.setGravity(0.0, 0.0, -9.81, physicsClientId=self.client_id)
        p.setTimeStep(self.time_step, physicsClientId=self.client_id)
        p.setPhysicsEngineParameter(
            numSolverIterations=30,
            numSubSteps=1,
            physicsClientId=self.client_id
        )

        if self.is_gui:
            # Clean view without sidebars, enable shadows
            p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_SHADOWS, 1, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_RGB_BUFFER_PREVIEW, 0, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_DEPTH_BUFFER_PREVIEW, 0, physicsClientId=self.client_id)
            p.configureDebugVisualizer(p.COV_ENABLE_SEGMENTATION_MARK_PREVIEW, 0, physicsClientId=self.client_id)
            self.reset_camera()

    def reset_camera(
        self,
        distance: float = 22.0,
        yaw: float = -45.0,
        pitch: float = -55.0,
        target_position: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> None:
        """Reset the debug visualizer camera looking down at warehouse."""
        if self.is_gui and self.is_connected:
            p.resetDebugVisualizerCamera(
                cameraDistance=distance,
                cameraYaw=yaw,
                cameraPitch=pitch,
                cameraTargetPosition=list(target_position),
                physicsClientId=self.client_id,
            )

    def step(self) -> None:
        """Perform a single physics simulation step."""
        if self.is_connected:
            p.stepSimulation(physicsClientId=self.client_id)

    def reset(self) -> None:
        """Reset the simulation world."""
        if self.is_connected:
            p.resetSimulation(physicsClientId=self.client_id)
            p.setGravity(0.0, 0.0, -9.81, physicsClientId=self.client_id)
            p.setTimeStep(self.time_step, physicsClientId=self.client_id)
            if self.is_gui:
                self.reset_camera()

    def close(self) -> None:
        """Disconnect and release physics client."""
        if self.is_connected and self.client_id >= 0:
            try:
                p.disconnect(physicsClientId=self.client_id)
            except Exception:
                pass
            self.is_connected = False
            self.client_id = -1
