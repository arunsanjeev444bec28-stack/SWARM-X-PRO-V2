"""
Master PyBullet 3D Warehouse Simulation Engine for SWARM-X PRO V2.
Orchestrates 3D physics, 78 racks, 98 RF nodes, 4 AMRs, 360-degree LiDARs,
node arbitration, dynamic obstacles, and live telemetry streaming.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.data.warehouse_real import (
    generate_rf_nodes,
    get_corner_rf_nodes,
)
from simulation.pybullet.world import SimulationWorld
from simulation.pybullet.warehouse import WarehousePhysicalModel
from simulation.pybullet.robot import AMRRobot
from simulation.pybullet.lidar import SimulatedLiDAR
from simulation.pybullet.physics import PhysicsEngine
from simulation.pybullet.controller import SimulationController
from simulation.pybullet.telemetry import TelemetryCollector
from edge_agents.simulation.controller import NodeArbitrationController

logger = logging.getLogger("simulation.engine")


class PyBulletSimulator:
    """Master simulator providing real-time 3D physics on Windows with PyBullet."""

    def __init__(
        self,
        gui: bool = True,
        target_fps: float = 30.0,
        lidar_hz: float = 10.0,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        replan_callback: Optional[Callable[[str, str, str, List[str]], Optional[List[str]]]] = None,
    ):
        self.requested_gui = gui
        self.target_fps = target_fps
        self.lidar_hz = lidar_hz
        self.event_callback = event_callback
        self.replan_callback = replan_callback

        self.is_running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Initialize subcomponents
        self.world = SimulationWorld(gui=self.requested_gui)
        self.warehouse = WarehousePhysicalModel(self.world.client_id)
        self.warehouse.build_world()

        self.rf_nodes = generate_rf_nodes()
        self.corners = get_corner_rf_nodes(self.rf_nodes)

        # 4 Autonomous AMRs spawned at authoritative corner nodes
        self.robots: Dict[str, AMRRobot] = {}
        self.lidars: Dict[str, SimulatedLiDAR] = {}
        self._init_four_amrs()

        # Arbitration & Controllers
        self.arbitration = NodeArbitrationController()
        self.controller = SimulationController(
            robots=self.robots,
            rf_nodes=self.rf_nodes,
            arbitration_controller=self.arbitration,
            event_callback=self._on_controller_event,
            replan_callback=self.replan_callback,
        )

        self.physics = PhysicsEngine(self.world.client_id, target_hz=target_fps)
        self.telemetry = TelemetryCollector(self.robots)

        # LiDAR scanning timing
        self.last_lidar_time = 0.0
        self.lidar_interval = 1.0 / self.lidar_hz

        # Last scan data per robot (shared with SLAM)
        self.latest_scans: Dict[str, Dict[str, Any]] = {}
        self.slam_update_callback: Optional[Callable[[str, Dict[str, Any], Dict[str, Any]], None]] = None

    def _init_four_amrs(self) -> None:
        """Spawn the 4 AMRs at authoritative corner nodes."""
        for rid in ["R1", "R2", "R3", "R4"]:
            corner_node_id = self.corners[rid]
            node = self.rf_nodes[corner_node_id]
            # Face inwards towards center aisle
            initial_yaw = 0.0
            if "RF_6" in corner_node_id:
                initial_yaw = -math.pi / 2.0  # Face South
            else:
                initial_yaw = math.pi / 2.0   # Face North

            robot = AMRRobot(
                robot_id=rid,
                initial_node=corner_node_id,
                initial_x=node.x,
                initial_y=node.y,
                initial_yaw=initial_yaw,
                client_id=self.world.client_id,
            )
            self.robots[rid] = robot

            # Attach 360-degree LiDAR
            lidar = SimulatedLiDAR(
                robot_id=rid,
                client_id=self.world.client_id,
                num_rays=180,
                max_range=10.0,
            )
            self.lidars[rid] = lidar

    def _on_controller_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle internal controller events."""
        if self.event_callback:
            try:
                self.event_callback(event_type, payload)
            except Exception as e:
                logger.error("Error in event callback: %s", e)

    def set_slam_callback(self, callback: Callable[[str, Dict[str, Any], Dict[str, Any]], None]) -> None:
        """Register SLAM processor callback."""
        self.slam_update_callback = callback

    def start(self) -> None:
        """Start the background simulation loop."""
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="PyBulletSimThread")
            self._thread.start()
            logger.info("PyBullet 3D Simulation engine started in background thread")

    def stop(self) -> None:
        """Stop the background simulation loop."""
        with self._lock:
            if not self.is_running:
                return
            self.is_running = False
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("PyBullet 3D Simulation engine stopped")

    def _run_loop(self) -> None:
        """Continuous physical simulation loop running at target FPS."""
        frame_interval = 1.0 / self.target_fps
        last_time = time.time()

        while not self._stop_event.is_set():
            t0 = time.time()
            dt = t0 - last_time
            last_time = t0

            try:
                # 1. Step physics & robot kinematics
                self.physics.step()
                self.controller.step(dt=min(dt, 0.1))

                # 2. Execute LiDAR scans at lidar_hz
                if (t0 - self.last_lidar_time) >= self.lidar_interval:
                    self.last_lidar_time = t0
                    self._execute_lidar_scans()
            except Exception as loop_ex:
                logger.error("Simulation loop error: %s", loop_ex)

            # 3. Regulate frame rate
            compute_time = time.time() - t0
            sleep_time = frame_interval - compute_time
            if sleep_time > 0:
                time.sleep(sleep_time)

    def step(self, dt: float = 0.033) -> None:
        """Step physics, kinematics, and LiDAR scans synchronously."""
        with self._lock:
            self.physics.step()
            self.controller.step(dt=min(dt, 0.1))
            self._execute_lidar_scans()

    def _execute_lidar_scans(self) -> None:
        """Run real geometric LiDAR ray-casting for all active AMRs."""
        for rid, robot in self.robots.items():
            if robot.is_failed:
                continue

            lidar = self.lidars[rid]
            scan = lidar.scan(
                robot_x=robot.x,
                robot_y=robot.y,
                robot_yaw=robot.yaw,
                robot_body_id=robot.body_id,
            )
            self.latest_scans[rid] = scan

            # Check if dynamic obstacle was detected in forward cone while moving
            if scan.get("obstacle_detected") and robot.speed > 0.05 and scan.get("forward_obstacle"):
                self.controller.handle_obstacle_detected(
                    robot_id=rid,
                    obstacle_info=scan["forward_obstacle"],
                )

            # Forward to SLAM engine if registered
            if self.slam_update_callback:
                pose_data = robot.get_pose()
                self.slam_update_callback(rid, pose_data, scan)

    def assign_route(self, robot_id: str, route: List[str], task_id: Optional[str] = None) -> bool:
        """Assign an A* navigation route to an AMR."""
        return self.controller.assign_mission(robot_id, route, task_id=task_id)

    def add_obstacle(self, x: float, y: float, obstacle_id: str = "OBS_1") -> int:
        """Spawn dynamic physical obstacle into an aisle."""
        return self.warehouse.add_obstacle(x, y, obstacle_id)

    def remove_obstacle(self, obstacle_id: str) -> bool:
        """Remove dynamic physical obstacle."""
        return self.warehouse.remove_obstacle(obstacle_id)

    def fail_robot(self, robot_id: str) -> bool:
        """Simulate hardware failure on specified robot."""
        robot = self.robots.get(robot_id)
        if robot:
            robot.fail()
            self._on_controller_event("ROBOT_FAILED", {
                "robot_id": robot_id,
                "node_id": robot.current_node,
                "task_id": robot.task_id,
            })
            return True
        return False

    def recover_robot(self, robot_id: str) -> bool:
        """Recover robot from failure."""
        robot = self.robots.get(robot_id)
        if robot:
            robot.recover()
            self._on_controller_event("ROBOT_RECOVERED", {
                "robot_id": robot_id,
                "node_id": robot.current_node,
            })
            return True
        return False

    def get_telemetry(self) -> Dict[str, Any]:
        """Fetch current fleet telemetry."""
        return self.telemetry.get_fleet_telemetry()

    def get_latest_scan(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Fetch latest raw LiDAR scan for specified robot."""
        return self.latest_scans.get(robot_id)

    def reset(self) -> None:
        """Reset the physical simulation state."""
        self.stop()
        self.warehouse.clear_dynamic_obstacles()
        for rid, robot in self.robots.items():
            corner_node = self.corners[rid]
            node = self.rf_nodes[corner_node]
            robot.recover()
            robot.x = node.x
            robot.y = node.y
            robot.current_node = corner_node
            robot.next_node = None
            robot.target_node = None
            robot.route = []
            robot.trajectory_history = [(node.x, node.y, time.time())]
            robot._apply_pose_to_pybullet()
            self.arbitration.occupancy[corner_node] = rid
        self.start()
