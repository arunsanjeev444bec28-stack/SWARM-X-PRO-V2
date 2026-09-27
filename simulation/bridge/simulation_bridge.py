"""
Simulation Bridge for SWARM-X PRO V2.
Bridges PyBullet physical simulation, 2D SLAM, Edge Agents, and FastAPI WebSocket broadcasting.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional

from simulation.pybullet.simulator import PyBulletSimulator
from simulation.slam.slam_engine import SlamEngine

logger = logging.getLogger("simulation.bridge")


class SimulationBridge:
    """Coordinates the PyBullet simulator with edge agent planning and FastAPI streaming."""

    def __init__(self, gui: bool = True, target_fps: float = 30.0):
        self.gui = gui
        self.target_fps = target_fps
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._broadcast_coro: Optional[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = None

        # Instantiate SLAM and PyBullet Simulator
        self.slam = SlamEngine(resolution=0.10)
        self.simulator = PyBulletSimulator(
            gui=self.gui,
            target_fps=self.target_fps,
            lidar_hz=10.0,
            event_callback=self._handle_sim_event,
            replan_callback=self._handle_replan_request,
        )

        # Connect SLAM to simulated LiDAR feed
        self.simulator.set_slam_callback(self.slam.process_scan)

        # Telemetry broadcasting thread
        self._telemetry_running = False
        self._telemetry_thread: Optional[threading.Thread] = None

    def set_broadcast_callback(
        self,
        coro: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """Register FastAPI WebSocket broadcaster."""
        self._broadcast_coro = coro
        self._loop = loop or asyncio.get_event_loop()

    def broadcast_sync(self, message: Dict[str, Any]) -> None:
        """Thread-safe dispatch to async WebSocket broadcaster."""
        if self._broadcast_coro and self._loop and self._loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self._broadcast_coro(message), self._loop)
            except Exception as e:
                logger.debug("Failed to schedule broadcast: %s", e)

    def _handle_sim_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Forward simulation event to WebSocket clients and global state."""
        from backend.core.state import global_state

        event_msg = {
            "event": event_type,
            "timestamp": time.time(),
            **payload,
        }
        global_state.events.append(event_msg)
        self.broadcast_sync(event_msg)

        # Synchronize robot state when entered node or changed status
        if "robot_id" in payload:
            rid = payload["robot_id"]
            robot_state = self.simulator.robots.get(rid)
            if robot_state:
                g_robot = global_state.get_robot(rid)
                if g_robot:
                    g_robot.node_id = robot_state.current_node
                    g_robot.status = robot_state.status
                    g_robot.position = [robot_state.x, robot_state.y, robot_state.z]
                    g_robot.battery = robot_state.battery

    def _handle_replan_request(
        self,
        robot_id: str,
        current_node: str,
        target_node: str,
        blocked_nodes: List[str],
    ) -> Optional[List[str]]:
        """
        Invoke the Edge Agent's local A* planner to replan around dynamic obstacle.
        Preserves decentralized architecture (Edge Agent makes the planning decision).
        """
        from edge_agents.fleet_coordinator import fleet_coordinator
        agent = fleet_coordinator.agents.get(robot_id)
        if not agent or not agent.local_planner:
            return None

        # Replan with blocked nodes penalized/avoided
        blocked_set = set(blocked_nodes)
        new_path = agent.local_planner.plan(
            start=current_node,
            goal=target_node,
            blocked=blocked_set,
        )
        if not new_path:
            new_path = agent.replan_path(
                current_path=[current_node, target_node],
                blocked=blocked_set,
                start_node=current_node,
                goal_node=target_node,
            )

        logger.info(
            "%s edge-agent replanned route from %s to %s avoiding %s -> %s",
            robot_id,
            current_node,
            target_node,
            blocked_nodes,
            new_path,
        )
        return new_path

    def start(self) -> None:
        """Start physical simulator and telemetry broadcast thread."""
        self.simulator.start()
        self.slam.start()
        if not self._telemetry_running:
            self._telemetry_running = True
            self._telemetry_thread = threading.Thread(
                target=self._telemetry_loop,
                daemon=True,
                name="SimBridgeTelemetry",
            )
            self._telemetry_thread.start()
        logger.info("SimulationBridge started")

    def stop(self) -> None:
        """Stop physical simulator and telemetry broadcast."""
        self._telemetry_running = False
        self.simulator.stop()
        self.slam.pause()
        if self._telemetry_thread and self._telemetry_thread.is_alive():
            self._telemetry_thread.join(timeout=1.0)
        logger.info("SimulationBridge stopped")

    def _telemetry_loop(self) -> None:
        """Periodically stream continuous telemetry & SLAM updates to WebSocket."""
        rate_hz = 15.0  # 15 telemetry packets / second
        interval = 1.0 / rate_hz
        slam_counter = 0

        while self._telemetry_running:
            t0 = time.time()

            # 1. Collect continuous robot telemetry
            fleet_data = self.simulator.get_telemetry()
            telemetry_msg = {
                "event": "SIMULATION_TELEMETRY",
                **fleet_data,
            }
            self.broadcast_sync(telemetry_msg)

            # Sync with global_state robots
            from backend.core.state import global_state
            for r_data in fleet_data.get("robots", []):
                if r_data:
                    rid = r_data["robot_id"]
                    g_robot = global_state.get_robot(rid)
                    if g_robot:
                        g_robot.position = [r_data["x"], r_data["y"], r_data["z"]]
                        g_robot.node_id = r_data["current_node"]
                        g_robot.status = r_data["status"]
                        g_robot.battery = r_data["battery"]

            # 2. Broadcast SLAM updates at ~5 Hz (every 3rd telemetry frame)
            slam_counter += 1
            if slam_counter >= 3:
                slam_counter = 0
                slam_state = self.slam.get_slam_state(include_grid=True, scale_down=2)
                slam_msg = {
                    "event": "SLAM_MAP_UPDATED",
                    "slam": slam_state,
                }
                self.broadcast_sync(slam_msg)

            elapsed = time.time() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def dispatch_route(self, robot_id: str, route: List[str], task_id: Optional[str] = None) -> bool:
        """Direct AMR to physically execute the assigned A* route in PyBullet."""
        success = self.simulator.assign_route(robot_id, route, task_id=task_id)
        if success:
            logger.info("Dispatched %s on PyBullet route: %s", robot_id, route)
        return success

    def add_dynamic_obstacle(self, x: float, y: float, obstacle_id: str = "OBS_1") -> Dict[str, Any]:
        """Inject dynamic obstacle in an aisle."""
        body_id = self.simulator.add_obstacle(x, y, obstacle_id)
        payload = {
            "obstacle_id": obstacle_id,
            "x": x,
            "y": y,
            "body_id": body_id,
        }
        self._handle_sim_event("OBSTACLE_ADDED", payload)
        return {"status": "success", **payload}

    def remove_dynamic_obstacle(self, obstacle_id: str) -> Dict[str, Any]:
        """Remove dynamic obstacle."""
        removed = self.simulator.remove_obstacle(obstacle_id)
        if removed:
            self._handle_sim_event("OBSTACLE_REMOVED", {"obstacle_id": obstacle_id})
        return {"status": "success" if removed else "not_found", "obstacle_id": obstacle_id}

    def fail_robot(self, robot_id: str) -> Dict[str, Any]:
        """
        Trigger robot failure.
        The robot immediately halts, and the edge-agent failure/heartbeat mechanisms
        detect the failure, re-opening the task for CBAA reauction.
        """
        ok = self.simulator.fail_robot(robot_id)
        if ok:
            from backend.core.state import global_state
            g_robot = global_state.get_robot(robot_id)
            if g_robot:
                g_robot.status = "FAILED"

            # Check if this robot had an active task to reopen
            failed_task_id = global_state.robot_tasks.pop(robot_id, None)
            if not failed_task_id:
                sim_robot = self.simulator.robots.get(robot_id)
                if sim_robot and sim_robot.task_id:
                    failed_task_id = sim_robot.task_id
            global_state.robot_paths.pop(robot_id, None)

            # Record failure in global_state
            global_state.failures.append({
                "robot_id": robot_id,
                "timestamp": time.time(),
                "task_id": failed_task_id,
            })

            # Broadcast failure
            self.broadcast_sync({
                "event": "ROBOT_FAILED",
                "robot_id": robot_id,
                "task_id": failed_task_id,
            })

            # If task was active, reopen for CBAA re-auction among surviving AMRs
            if failed_task_id and failed_task_id in global_state.tasks:
                task = global_state.tasks[failed_task_id]
                logger.info("Reopening task %s due to failure of %s", failed_task_id, robot_id)
                self.broadcast_sync({
                    "event": "TASK_REOPENED",
                    "task_id": failed_task_id,
                    "reason": f"Carrier {robot_id} failed",
                })
                # Decentralized re-auction among available edge agents
                from edge_agents.fleet_coordinator import fleet_coordinator
                task_dict = task.model_dump() if hasattr(task, "model_dump") else dict(task)
                alloc_res = fleet_coordinator.announce_and_allocate_task(task_dict)
                new_winner = alloc_res.get("winner")
                new_path = alloc_res.get("path", [])

                if new_winner and new_winner != robot_id:
                    global_state.robot_tasks[new_winner] = failed_task_id
                    w_robot = global_state.get_robot(new_winner)
                    if w_robot:
                        w_robot.status = "DISPATCHING"

                    self.dispatch_route(new_winner, new_path, task_id=failed_task_id)

                    self.broadcast_sync({
                        "event": "TASK_REASSIGNED",
                        "task_id": failed_task_id,
                        "old_winner": robot_id,
                        "new_winner": new_winner,
                        "new_route": new_path,
                    })

            return {
                "status": "success",
                "robot_id": robot_id,
                "reopened_task": failed_task_id,
                "new_winner": new_winner if 'new_winner' in locals() else None,
                "new_route": new_path if 'new_path' in locals() else [],
            }

        return {"status": "error", "message": f"Robot {robot_id} not found"}

    def recover_robot(self, robot_id: str) -> Dict[str, Any]:
        """Recover a failed robot."""
        ok = self.simulator.recover_robot(robot_id)
        if ok:
            from backend.core.state import global_state
            g_robot = global_state.get_robot(robot_id)
            if g_robot:
                g_robot.status = "AVAILABLE"
                g_robot.battery = 100.0
            self.broadcast_sync({
                "event": "ROBOT_RECOVERED",
                "robot_id": robot_id,
            })
            return {"status": "success", "robot_id": robot_id}
        return {"status": "error", "message": f"Robot {robot_id} not found"}

    def reset_simulation(self) -> Dict[str, Any]:
        """Reset simulator, warehouse state, and SLAM map."""
        self.simulator.reset()
        self.slam.reset_map()
        self.slam.clear_trajectory()

        from backend.core.state import global_state
        from backend.data.warehouse_real import init_real_warehouse_state
        from edge_agents.fleet_coordinator import fleet_coordinator

        init_real_warehouse_state(global_state)
        fleet_coordinator.update_graph_and_corners(
            global_state.nodes,
            {r.robot_id: r.node_id for r in global_state.get_all_robots()},
        )

        self.broadcast_sync({"event": "SIMULATION_RESET"})
        return {"status": "success"}


# Lazy global singleton
_bridge_instance: Optional[SimulationBridge] = None

def get_sim_bridge(gui: bool = True) -> SimulationBridge:
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = SimulationBridge(gui=gui)
    return _bridge_instance

class _LazySimBridge:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_sim_bridge(), name)

sim_bridge = _LazySimBridge()
