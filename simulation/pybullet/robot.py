"""
Physical 3D Autonomous Mobile Robot (AMR) Model for PyBullet.
Implements continuous physical kinematics, turn-in-place at RF nodes,
LiDAR sensor mounting, and visual status indicators.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import pybullet as p

logger = logging.getLogger("simulation.robot")

ROBOT_COLORS = {
    "R1": [0.10, 0.50, 0.95, 1.0],  # Cyan / Blue
    "R2": [0.98, 0.55, 0.10, 1.0],  # Safety Orange / Amber
    "R3": [0.15, 0.85, 0.40, 1.0],  # Emerald Green
    "R4": [0.75, 0.25, 0.95, 1.0],  # Industrial Purple
}

STATUS_COLORS = {
    "AVAILABLE": [0.1, 0.8, 0.1],
    "IDLE": [0.1, 0.8, 0.1],
    "MOVING": [0.0, 0.7, 1.0],
    "DISPATCHING": [0.0, 0.7, 1.0],
    "TRANSPORTING": [0.9, 0.6, 0.0],
    "WAITING": [1.0, 0.8, 0.0],
    "WAIT": [1.0, 0.8, 0.0],
    "FAILED": [0.9, 0.1, 0.1],
}


class AMRRobot:
    """Simulates a continuous physical AMR moving through the PyBullet warehouse."""

    def __init__(
        self,
        robot_id: str,
        initial_node: str,
        initial_x: float,
        initial_y: float,
        initial_yaw: float = 0.0,
        client_id: int = 0,
        max_speed: float = 1.0,
        max_angular_speed: float = 2.5,
    ):
        self.robot_id = robot_id
        self.current_node = initial_node
        self.next_node: Optional[str] = None
        self.target_node: Optional[str] = None
        self.client_id = client_id

        # Motion parameters
        self.max_speed = max_speed                     # 1.0 m/s nominal
        self.max_angular_speed = max_angular_speed     # 2.5 rad/s
        self.acceleration = 1.5                        # m/s^2

        # Physical state
        self.x = float(initial_x)
        self.y = float(initial_y)
        self.z = 0.12  # Half of chassis height + wheel radius
        self.yaw = float(initial_yaw)
        self.speed = 0.0
        self.angular_velocity = 0.0

        # Operational status
        self.status = "AVAILABLE"
        self.battery = 100.0
        self.temperature = 25.0
        self.load = 0.0
        self.task_id: Optional[str] = None
        self.is_failed = False
        self.is_waiting = False

        # Route navigation
        self.route: List[str] = []
        self.route_index: int = 0
        self.target_waypoint: Optional[Tuple[float, float]] = None
        self.node_resolver: Optional[Callable[[str], Optional[Tuple[float, float]]]] = None

        # Trajectory history
        self.trajectory_history: List[Tuple[float, float, float]] = [(self.x, self.y, time.time())]

        # PyBullet body IDs
        self.body_id = -1
        self.debug_text_id = -1
        self._spawn_robot_body()

    def _spawn_robot_body(self) -> None:
        """Create visually detailed AMR with chassis, wheels, LiDAR turret, and front beacon."""
        chassis_l = 0.60
        chassis_w = 0.40
        chassis_h = 0.18
        wheel_r = 0.06
        wheel_w = 0.04
        lidar_r = 0.07
        lidar_h = 0.06

        color = ROBOT_COLORS.get(self.robot_id, [0.5, 0.5, 0.5, 1.0])

        # Base chassis collision & visual
        col_chassis = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=[chassis_l / 2.0, chassis_w / 2.0, chassis_h / 2.0],
            physicsClientId=self.client_id,
        )
        vis_chassis = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[chassis_l / 2.0, chassis_w / 2.0, chassis_h / 2.0],
            rgbaColor=color,
            physicsClientId=self.client_id,
        )

        # Child links:
        # 0: LiDAR puck on top
        # 1: Front directional arrow/beacon
        # 2: Left front wheel
        # 3: Right front wheel
        # 4: Left rear wheel
        # 5: Right rear wheel
        vis_lidar = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=lidar_r,
            length=lidar_h,
            rgbaColor=[0.15, 0.15, 0.18, 1.0],  # Dark metallic sensor housing
            physicsClientId=self.client_id,
        )
        vis_front = p.createVisualShape(
            p.GEOM_BOX,
            halfExtents=[0.05, chassis_w / 3.0, chassis_h / 3.0],
            rgbaColor=[1.0, 1.0, 0.2, 1.0],     # High-vis yellow front bumper
            physicsClientId=self.client_id,
        )
        wheel_vis = p.createVisualShape(
            p.GEOM_CYLINDER,
            radius=wheel_r,
            length=wheel_w,
            rgbaColor=[0.1, 0.1, 0.1, 1.0],     # Black rubber wheel
            physicsClientId=self.client_id,
        )

        link_masses = [0.1] * 6
        link_col_shapes = [-1] * 6
        link_vis_shapes = [vis_lidar, vis_front, wheel_vis, wheel_vis, wheel_vis, wheel_vis]

        wheel_x = chassis_l / 3.0
        wheel_y = chassis_w / 2.0 + wheel_w / 2.0
        wheel_z = -chassis_h / 2.0 + wheel_r / 2.0

        # Rotate wheels so cylinders face horizontally along Y
        wheel_orn = p.getQuaternionFromEuler([math.pi / 2.0, 0, 0])

        link_positions = [
            [0.0, 0.0, chassis_h / 2.0 + lidar_h / 2.0],        # LiDAR
            [chassis_l / 2.0 + 0.02, 0.0, 0.0],                 # Front bumper
            [wheel_x, wheel_y, wheel_z],                        # Front-left
            [wheel_x, -wheel_y, wheel_z],                       # Front-right
            [-wheel_x, wheel_y, wheel_z],                       # Rear-left
            [-wheel_x, -wheel_y, wheel_z],                      # Rear-right
        ]
        link_orientations = [
            [0, 0, 0, 1],
            [0, 0, 0, 1],
            wheel_orn,
            wheel_orn,
            wheel_orn,
            wheel_orn,
        ]

        quat = p.getQuaternionFromEuler([0, 0, self.yaw])
        self.body_id = p.createMultiBody(
            baseMass=25.0,  # 25 kg industrial AMR
            baseCollisionShapeIndex=col_chassis,
            baseVisualShapeIndex=vis_chassis,
            basePosition=[self.x, self.y, self.z],
            baseOrientation=quat,
            linkMasses=link_masses,
            linkCollisionShapeIndices=link_col_shapes,
            linkVisualShapeIndices=link_vis_shapes,
            linkPositions=link_positions,
            linkOrientations=link_orientations,
            linkInertialFramePositions=[[0, 0, 0]] * 6,
            linkInertialFrameOrientations=[[0, 0, 0, 1]] * 6,
            linkParentIndices=[0] * 6,
            linkJointTypes=[p.JOINT_FIXED] * 6,
            linkJointAxis=[[0, 0, 1]] * 6,
            physicsClientId=self.client_id,
        )

        self._update_debug_text()

    def _update_debug_text(self) -> None:
        """Draw 3D overhead label with Robot ID and Status in PyBullet."""
        try:
            status_col = STATUS_COLORS.get(self.status, [1.0, 1.0, 1.0])
            text = f"{self.robot_id} [{self.status}]"
            pos = [self.x, self.y, self.z + 0.50]
            if self.debug_text_id >= 0:
                p.removeUserDebugItem(self.debug_text_id, physicsClientId=self.client_id)
            self.debug_text_id = p.addUserDebugText(
                text=text,
                textPosition=pos,
                textColorRGB=status_col,
                textSize=1.1,
                lifeTime=0,
                physicsClientId=self.client_id,
            )
        except Exception:
            pass

    def set_route(
        self,
        route: List[str],
        node_resolver: Callable[[str], Optional[Tuple[float, float]]],
        task_id: Optional[str] = None,
    ) -> None:
        """Assign an A* navigation route produced by the edge agent."""
        self.route = list(route)
        self.node_resolver = node_resolver
        self.task_id = task_id
        self.route_index = 0
        self.is_waiting = False

        if len(self.route) > 1:
            # If currently at start of route, advance to first step
            if self.route[0] == self.current_node:
                self.route_index = 1
            else:
                self.route_index = 0

            self.next_node = self.route[self.route_index]
            self.target_node = self.route[-1]
            coords = self.node_resolver(self.next_node)
            if coords:
                self.target_waypoint = coords
            self.status = "MOVING"
        elif len(self.route) == 1:
            self.next_node = self.route[0]
            self.target_node = self.route[0]
            coords = self.node_resolver(self.next_node)
            if coords:
                self.target_waypoint = coords
            self.status = "AVAILABLE"
        else:
            self.next_node = None
            self.target_node = None
            self.target_waypoint = None
            self.status = "AVAILABLE"

        self._update_debug_text()
        logger.info("%s assigned route: %s (task: %s)", self.robot_id, self.route, self.task_id)

    def stop(self) -> None:
        """Command AMR to halt immediately."""
        self.speed = 0.0
        self.angular_velocity = 0.0
        if not self.is_failed:
            self.status = "WAITING"
        self._update_debug_text()

    def wait(self, reason: str = "") -> None:
        """Put robot into waiting state due to contested RF node or yield."""
        self.is_waiting = True
        self.speed = 0.0
        self.angular_velocity = 0.0
        self.status = "WAITING"
        self._update_debug_text()
        logger.info("%s waiting: %s", self.robot_id, reason)

    def resume(self) -> None:
        """Resume movement along planned route after clearance."""
        self.is_waiting = False
        if self.route and self.route_index < len(self.route):
            self.status = "MOVING"
        else:
            self.status = "AVAILABLE"
        self._update_debug_text()

    def fail(self) -> None:
        """Simulate hardware failure: stop motion, mark FAILED status."""
        self.is_failed = True
        self.speed = 0.0
        self.angular_velocity = 0.0
        self.status = "FAILED"
        self.battery = max(0.0, self.battery - 10.0)
        self._update_debug_text()
        logger.warning("Simulated failure triggered on %s", self.robot_id)

    def recover(self) -> None:
        """Recover robot from failure."""
        self.is_failed = False
        self.is_waiting = False
        self.status = "AVAILABLE"
        self.route = []
        self.route_index = 0
        self.next_node = None
        self.target_node = None
        self.target_waypoint = None
        self._update_debug_text()
        logger.info("%s recovered from failure", self.robot_id)

    def update_kinematics(
        self,
        dt: float,
        on_node_arrival: Optional[Callable[[str, str, str], None]] = None,
        can_enter_node_check: Optional[Callable[[str, str, str], bool]] = None,
    ) -> bool:
        """
        Advance physical continuous kinematics.
        Turns only at RF nodes.
        Returns True if a node was reached during this step.
        """
        if self.is_failed or self.is_waiting or not self.target_waypoint:
            self.speed = 0.0
            return False

        tx, ty = self.target_waypoint
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)

        # Check node arrival threshold
        arrival_threshold = 0.05  # 5 cm
        if dist <= arrival_threshold:
            # Arrived at waypoint
            arrived_node = self.next_node or self.current_node
            previous_node = self.current_node
            self.current_node = arrived_node
            self.x = tx
            self.y = ty
            self.speed = 0.0

            # Advance to next route waypoint
            self.route_index += 1
            node_reached = True

            if on_node_arrival:
                on_node_arrival(self.robot_id, previous_node, arrived_node)

            if self.route_index < len(self.route):
                next_step = self.route[self.route_index]
                # Check arbitration gatekeeper before advancing
                if can_enter_node_check and not can_enter_node_check(self.robot_id, arrived_node, next_step):
                    # Must wait at current node!
                    self.wait(f"Contested entry into {next_step}")
                    return True

                self.next_node = next_step
                coords = self.node_resolver(self.next_node) if self.node_resolver else None
                if coords:
                    self.target_waypoint = coords
            else:
                # Completed route!
                self.next_node = None
                self.target_node = None
                self.target_waypoint = None
                self.status = "AVAILABLE"
                self.route = []
                self._update_debug_text()

            self._apply_pose_to_pybullet()
            return True

        # Calculate desired heading towards next RF node
        target_yaw = math.atan2(dy, dx)
        yaw_err = (target_yaw - self.yaw + math.pi) % (2.0 * math.pi) - math.pi

        # Visible turn-in-place at RF node:
        # If heading error exceeds threshold (~4 degrees), rotate in place first!
        turn_threshold = 0.07  # ~4 degrees
        if abs(yaw_err) > turn_threshold:
            turn_direction = 1.0 if yaw_err > 0 else -1.0
            turn_amount = min(abs(yaw_err), self.max_angular_speed * dt)
            self.yaw += turn_direction * turn_amount
            self.yaw = (self.yaw + math.pi) % (2.0 * math.pi) - math.pi
            self.speed = 0.0  # Zero forward speed while turning
        else:
            # Oriented towards waypoint: drive forward smoothly
            self.yaw = target_yaw
            step_dist = min(dist, self.max_speed * dt)
            self.speed = step_dist / dt if dt > 0 else self.max_speed
            self.x += step_dist * math.cos(self.yaw)
            self.y += step_dist * math.sin(self.yaw)

            # Record trajectory
            if not self.trajectory_history or math.hypot(self.x - self.trajectory_history[-1][0], self.y - self.trajectory_history[-1][1]) > 0.15:
                self.trajectory_history.append((round(self.x, 3), round(self.y, 3), time.time()))

        # Natural battery drain while active
        self.battery = max(0.0, self.battery - (0.005 * dt if self.speed > 0 else 0.001 * dt))

        self._apply_pose_to_pybullet()
        return False

    def _apply_pose_to_pybullet(self) -> None:
        """Sync internal continuous pose with PyBullet multi-body transform."""
        quat = p.getQuaternionFromEuler([0, 0, self.yaw])
        p.resetBasePositionAndOrientation(
            self.body_id,
            [self.x, self.y, self.z],
            quat,
            physicsClientId=self.client_id,
        )
        self._update_debug_text()

    def get_pose(self) -> Dict[str, Any]:
        """Return snapshot of continuous robot pose and state."""
        return {
            "robot_id": self.robot_id,
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "yaw": round(self.yaw, 3),
            "speed": round(self.speed, 2),
            "current_node": self.current_node,
            "next_node": self.next_node,
            "target_node": self.target_node,
            "status": self.status,
            "battery": round(self.battery, 1),
            "task_id": self.task_id,
            "route": list(self.route),
        }
