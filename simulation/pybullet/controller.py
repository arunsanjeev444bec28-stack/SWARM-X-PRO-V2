"""
Simulation Controller for SWARM-X PRO V2.
Coordinates the 4 AMRs, delegates node-entry arbitration to NodeArbitrationController,
monitors continuous kinematics, handles dynamic obstacle replanning, and processes failures.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from edge_agents.simulation.controller import NodeArbitrationController
from simulation.pybullet.robot import AMRRobot

logger = logging.getLogger("simulation.controller")


class SimulationController:
    """Orchestrates AMR physical navigation, RF node arbitration, and obstacle replanning."""

    def __init__(
        self,
        robots: Dict[str, AMRRobot],
        rf_nodes: Dict[str, Any],
        arbitration_controller: Optional[NodeArbitrationController] = None,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        replan_callback: Optional[Callable[[str, str, str, List[str]], Optional[List[str]]]] = None,
    ):
        self.robots = robots
        self.rf_nodes = rf_nodes
        self.arbitration = arbitration_controller or NodeArbitrationController()
        self.event_callback = event_callback
        self.replan_callback = replan_callback

        # Register all robots in arbitration occupancy registry
        for rid, robot in self.robots.items():
            self.arbitration.occupancy[robot.current_node] = rid

    def resolve_node_coords(self, node_id: str) -> Optional[Tuple[float, float]]:
        """Lookup (x, y) coordinates for an RF node."""
        node = self.rf_nodes.get(node_id)
        if node:
            nx = getattr(node, "x", None) or (node.get("x") if isinstance(node, dict) else 0.0)
            ny = getattr(node, "y", None) or (node.get("y") if isinstance(node, dict) else 0.0)
            return (float(nx), float(ny))
        return None

    def emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Forward simulation event to event callback and arbitration logger."""
        self.arbitration.log_event(event_type, payload)
        if self.event_callback:
            try:
                self.event_callback(event_type, payload)
            except Exception as e:
                logger.error("Error in event callback: %s", e)

    def can_enter_node(self, robot_id: str, current_node: str, next_node: str) -> bool:
        """Query node arbitration gatekeeper before robot enters next RF node."""
        allowed = self.arbitration.can_enter_node(
            robot_id=robot_id,
            current_node=current_node,
            next_node=next_node,
            eta=1.0,
        )
        if not allowed:
            self.emit_event("WAIT", {
                "robot_id": robot_id,
                "current_node": current_node,
                "next_node": next_node,
                "reason": f"Node {next_node} contested or occupied",
            })
        return allowed

    def on_node_arrival(self, robot_id: str, previous_node: str, current_node: str) -> None:
        """Handle physical arrival at an RF intersection node."""
        self.arbitration.on_node_reached(robot_id, previous_node, current_node)
        self.emit_event("ENTER_NODE", {
            "robot_id": robot_id,
            "node_id": current_node,
            "from_node": previous_node,
        })

        # Check if other waiting robots can now enter previous_node
        for other_id, other_robot in self.robots.items():
            if other_id != robot_id and other_robot.is_waiting and other_robot.next_node == previous_node:
                if self.arbitration.can_enter_node(other_id, other_robot.current_node, previous_node):
                    other_robot.resume()
                    self.emit_event("RESUME", {
                        "robot_id": other_id,
                        "node_id": previous_node,
                    })

    def assign_mission(self, robot_id: str, route: List[str], task_id: Optional[str] = None) -> bool:
        """Assign an A* planned route to an AMR."""
        robot = self.robots.get(robot_id)
        if not robot or robot.is_failed:
            return False

        robot.set_route(route, self.resolve_node_coords, task_id=task_id)
        # Register upcoming intent with arbitration
        if len(route) > 1:
            self.arbitration.register_intent(
                robot_id=robot_id,
                current_node=robot.current_node,
                next_node=route[1] if route[0] == robot.current_node else route[0],
                planned_path=route,
            )
        return True

    def handle_obstacle_detected(
        self,
        robot_id: str,
        obstacle_info: Dict[str, Any],
        blocked_nodes: Optional[List[str]] = None,
    ) -> None:
        """
        Handle dynamic obstacle detected ahead of robot by LiDAR.
        Stops robot, triggers edge-agent A* replanning, updates route.
        """
        robot = self.robots.get(robot_id)
        if not robot or not robot.route or robot.is_failed:
            return

        robot.stop()
        self.emit_event("OBSTACLE_DETECTED", {
            "robot_id": robot_id,
            "current_node": robot.current_node,
            "next_node": robot.next_node,
            "distance": obstacle_info.get("distance"),
            "obstacle_point": obstacle_info.get("point"),
        })

        # Request edge agent to replan around obstacle
        if self.replan_callback and robot.next_node and robot.target_node:
            self.emit_event("REPLANNING", {
                "robot_id": robot_id,
                "current_node": robot.current_node,
                "target_node": robot.target_node,
                "blocked_node": robot.next_node,
            })
            new_path = self.replan_callback(
                robot_id,
                robot.current_node,
                robot.target_node,
                blocked_nodes or [robot.next_node],
            )
            if new_path and len(new_path) >= 1:
                robot.set_route(new_path, self.resolve_node_coords, task_id=robot.task_id)
                self.emit_event("NEW_ROUTE", {
                    "robot_id": robot_id,
                    "new_path": new_path,
                })
                robot.resume()
            else:
                logger.warning("Replanning for %s found no alternative path!", robot_id)

    def step(self, dt: float) -> None:
        """Advance all active AMRs by dt."""
        for rid, robot in self.robots.items():
            if robot.is_failed:
                continue

            robot.update_kinematics(
                dt=dt,
                on_node_arrival=self.on_node_arrival,
                can_enter_node_check=self.can_enter_node,
            )
