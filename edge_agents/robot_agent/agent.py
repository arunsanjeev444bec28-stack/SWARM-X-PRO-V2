from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from edge_agents.common.adapters import adapt_robot_payload, adapt_task_payload
from edge_agents.common.state import NeighborState, RobotState
from edge_agents.communication.protocol import MessageEnvelope
from edge_agents.config.default import EDGE_AGENT_CONFIG
from edge_agents.coordination.cbaa import LocalCBAA
from edge_agents.planning.local_planner import LocalPlanner


@dataclass
class TaskEnvelope:
    task_id: str
    pickup_node: str
    dispatch_node: str
    priority: str = "NORMAL"
    urgency: float = 1.0
    deadline: float = 100.0
    load: float = 1.0
    energy_requirement: float = 10.0


class EdgeRobotAgent:
    """Robot-local edge agent boundary.

    This class intentionally does not replace the global backend simulation. It
    exists as an independent process boundary for local decision-making.
    """

    DEFAULT_GRAPH = {
        "N_0_0": {"N_0_1": 1.0},
        "N_0_1": {"N_0_0": 1.0, "N_0_2": 1.0},
        "N_0_2": {"N_0_1": 1.0, "N_0_3": 1.0},
        "N_0_3": {"N_0_2": 1.0},
    }

    @staticmethod
    def _priority_rank(priority: Any) -> int:
        name = str(priority).upper()
        return {"CRITICAL": 4, "HIGH": 3, "NORMAL": 2, "LOW": 1}.get(name, 2)

    @staticmethod
    def arbitrate_intersection(requests: List[Dict[str, Any]]) -> Optional[str]:
        if not requests:
            return None
        ranked = sorted(
            requests,
            key=lambda req: (
                -EdgeRobotAgent._priority_rank(req.get("priority", "NORMAL")),
                float(req.get("eta", float("inf"))),
                str(req.get("robot_id", "")),
            ),
        )
        return str(ranked[0].get("robot_id"))

    @staticmethod
    def detect_wait_cycle(wait_map: Dict[str, str]) -> Dict[str, Any]:
        if not wait_map:
            return {"cycle_detected": False, "cycle": [], "recovery_robot": None}

        seen: Dict[str, int] = {}
        for robot_id in sorted(wait_map):
            if robot_id in seen:
                continue
            path: List[str] = []
            current = robot_id
            while current in wait_map and current not in seen:
                seen[current] = len(path)
                path.append(current)
                current = str(wait_map[current])
            if current in seen:
                cycle = path[seen[current]:]
                if cycle:
                    recovery = min(cycle)
                    return {"cycle_detected": True, "cycle": cycle, "recovery_robot": recovery}
        return {"cycle_detected": False, "cycle": [], "recovery_robot": None}

    def __init__(self, robot_id: str, robot_data: Optional[Dict[str, Any]] = None):
        self.robot_id = robot_id
        self.config = EDGE_AGENT_CONFIG
        self.robot_data = robot_data or {
            "robot_id": robot_id,
            "node_id": "N_0_0",
            "battery": 100.0,
            "temperature": 25.0,
            "load": 0.0,
            "health": 100.0,
            "status": "IDLE",
        }
        self.state = RobotState(
            robot_id=robot_id,
            timestamp=time.time(),
            x=0.0,
            y=0.0,
            heading=0.0,
            linear_velocity=0.0,
            angular_velocity=0.0,
            battery=float(self.robot_data.get("battery", 100.0)),
            status=str(self.robot_data.get("status", "IDLE")),
            current_task_id=None,
            target_node=None,
            current_node=str(self.robot_data.get("node_id", "N_0_0")),
            planned_path=[],
            current_path_index=0,
        )
        self.neighbors: Dict[str, NeighborState] = {}
        self.local_tasks: Dict[str, TaskEnvelope] = {}
        self.local_bid_cache: Dict[str, Dict[str, Any]] = {}
        self.task_bids: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.task_ownership: Dict[str, Optional[str]] = {}
        self.task_reopened: Set[str] = set()
        self.last_seq = 0
        self.local_planner = LocalPlanner(self.DEFAULT_GRAPH)
        self.cbaa = LocalCBAA()
        self.failure_state = "HEALTHY"
        self.last_heartbeat = time.time()

    def update_from_backend_state(self, robot_data: Dict[str, Any]) -> None:
        self.robot_data = robot_data
        self.state.battery = float(robot_data.get("battery", self.state.battery))
        self.state.status = str(robot_data.get("status", self.state.status))
        self.state.current_node = str(robot_data.get("node_id", self.state.current_node))

    def add_task(self, task: Dict[str, Any] | TaskEnvelope) -> None:
        if isinstance(task, TaskEnvelope):
            self.local_tasks[task.task_id] = task
        else:
            self.local_tasks[str(task.get("task_id"))] = TaskEnvelope(
                task_id=str(task.get("task_id")),
                pickup_node=str(task.get("pickup_node")),
                dispatch_node=str(task.get("dispatch_node")),
                priority=str(task.get("priority", "NORMAL")),
                urgency=float(task.get("urgency", 1.0)),
                deadline=float(task.get("deadline", 100.0)),
                load=float(task.get("load", 1.0)),
                energy_requirement=float(task.get("energy_requirement", 10.0)),
            )

    def feasibility(self, task_id: str) -> bool:
        task = self.local_tasks.get(task_id)
        if not task:
            return False
        return self.state.battery - task.energy_requirement >= 5.0

    def estimate_cost(self, task_id: str) -> float:
        task = self.local_tasks.get(task_id)
        if not task:
            return float("inf")
        if task.pickup_node == task.dispatch_node:
            return 0.0
        return 1.0

    def calculate_bid(self, task_id: str) -> Dict[str, Any]:
        task = self.local_tasks.get(task_id)
        if not task:
            return {"task_id": task_id, "feasible": False, "bid": float("inf"), "reason": "task missing"}

        feasible = self.feasibility(task_id)
        estimated_cost = self.estimate_cost(task_id)
        if not feasible:
            return {"task_id": task_id, "feasible": False, "bid": float("inf"), "reason": "battery reserve not met"}

        priority_map = {"LOW": 1, "NORMAL": 2, "HIGH": 3, "CRITICAL": 4}
        priority_value = priority_map.get(task.priority.upper(), 2)
        urg = float(task.urgency)
        battery_penalty = max(0.0, 100.0 - self.state.battery)
        # Energy removed from CBAA bid calculation.
        bid = (estimated_cost * 1.0) + (battery_penalty * 0.3) - (priority_value * urg * 0.4)

        result = {
            "task_id": task_id,
            "feasible": True,
            "estimated_cost": estimated_cost,
            "bid": bid,
            "reason": "OK",
            "robot_id": self.robot_id,
        }
        self.local_bid_cache[task_id] = result
        return result

    def register_bid(self, task_id: str, bid: Dict[str, Any]) -> Dict[str, Any]:
        self.task_bids.setdefault(task_id, {})[self.robot_id] = bid
        return bid

    def announce_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(task["task_id"])
        self.add_task(task)
        local_bid = self.calculate_bid(task_id)
        self.register_bid(task_id, local_bid)
        return local_bid

    def record_peer_bid(self, task_id: str, robot_id: str, bid: Dict[str, Any]) -> None:
        self.task_bids.setdefault(task_id, {})[robot_id] = bid

    def determine_task_winner(self, task_id: str, bids: Optional[Dict[str, Dict[str, Any]]] = None) -> Optional[str]:
        task_bids = self.task_bids.get(task_id, {}) if bids is None else bids
        valid = {rid: info for rid, info in task_bids.items() if info.get("feasible", False)}
        if not valid:
            return None
        winner, _ = sorted(valid.items(), key=lambda item: (float(item[1].get("bid", float("inf"))), item[0]))[0]
        self.task_ownership[task_id] = winner
        self.state.current_task_id = task_id if winner == self.robot_id else self.state.current_task_id
        return winner

    def determine_winner(self, bids: Dict[str, Dict[str, Any]]) -> Optional[str]:
        valid = {rid: info for rid, info in bids.items() if info.get("feasible", False)}
        if not valid:
            return None
        return sorted(valid.items(), key=lambda item: (float(item[1].get("bid", float("inf"))), item[0]))[0][0]

    def claim_winner(self, task_id: str, winner_id: str) -> Optional[str]:
        self.task_ownership[task_id] = winner_id
        if winner_id == self.robot_id:
            self.state.current_task_id = task_id
        return winner_id

    def handle_dead_robot(self, dead_robot_id: str, task_id: Optional[str] = None) -> bool:
        if task_id is not None:
            if task_id in self.task_bids and dead_robot_id in self.task_bids[task_id]:
                self.task_bids[task_id].pop(dead_robot_id, None)
            if self.task_ownership.get(task_id) == dead_robot_id:
                self.task_ownership[task_id] = None
                self.task_reopened.add(task_id)
                return True
            return False
        reopened = False
        for owned_task_id, owner in list(self.task_ownership.items()):
            if owned_task_id in self.task_bids and dead_robot_id in self.task_bids[owned_task_id]:
                self.task_bids[owned_task_id].pop(dead_robot_id, None)
            if owner == dead_robot_id:
                self.task_ownership[owned_task_id] = None
                self.task_reopened.add(owned_task_id)
                reopened = True
        return reopened

    def reopen_task(self, task_id: str) -> None:
        self.task_ownership[task_id] = None
        self.task_reopened.add(task_id)

    def calculate_path(
        self,
        task: Optional[Dict[str, Any]],
        start_node: Optional[str] = None,
        blocked: Optional[set[str]] = None,
        goal_node: Optional[str] = None,
    ) -> List[str]:
        if task is None:
            return []
        origin = start_node or self.state.current_node or "N_0_0"
        target = goal_node or str(task.get("pickup_node") or task.get("dispatch_node") or self.state.target_node or origin)
        path = self.local_planner.plan(origin, target, blocked=blocked or set())
        self.state.target_node = target
        self.state.planned_path = path
        self.state.current_path_index = 0
        return path

    def replan_path(
        self,
        current_path: Optional[List[str]],
        blocked: Optional[set[str]] = None,
        start_node: Optional[str] = None,
        goal_node: Optional[str] = None,
    ) -> List[str]:
        if not current_path:
            return []
        if blocked and any(node in blocked for node in current_path):
            origin = start_node or self.state.current_node or current_path[0]
            target = goal_node or current_path[-1]
            path = self.local_planner.plan(origin, target, blocked=blocked or set())
            self.state.planned_path = path or current_path
            self.state.current_path_index = 0
            return path or current_path
        self.state.planned_path = list(current_path)
        self.state.current_path_index = min(self.state.current_path_index, len(current_path) - 1)
        return list(current_path)

    def build_intent(
        self,
        task_id: str,
        current_node: str,
        next_node: str,
        planned_path: Optional[List[str]] = None,
        eta: float = 0.0,
        priority: str = "NORMAL",
    ) -> Dict[str, Any]:
        payload = {
            "robot_id": self.robot_id,
            "task_id": task_id,
            "current_node": current_node,
            "next_node": next_node,
            "planned_path": list(planned_path or [current_node, next_node]),
            "eta": float(eta),
            "priority": str(priority).upper(),
        }
        return {
            "msg_type": "INTENT",
            "sender_id": self.robot_id,
            "seq": self.next_seq(),
            "timestamp": time.time(),
            "payload": payload,
        }

    def should_wait_for_neighbor(self, neighbor: Optional[NeighborState], next_node: Optional[str]) -> bool:
        if not neighbor or not next_node:
            return False
        if neighbor.current_node == next_node:
            return True
        if neighbor.target_node == next_node:
            return True
        if neighbor.current_node and neighbor.target_node and neighbor.current_node in self.state.planned_path and neighbor.target_node in self.state.planned_path:
            return True
        return False

    def update_neighbor(self, neighbor_id: str, state: Dict[str, Any]) -> None:
        self.neighbors[neighbor_id] = NeighborState(
            robot_id=neighbor_id,
            last_seen=float(state.get("timestamp", time.time())),
            status=str(state.get("status", "UNKNOWN")),
            battery=state.get("battery"),
            current_task_id=state.get("current_task_id"),
            target_node=state.get("target_node"),
            current_node=state.get("current_node"),
            distance_m=state.get("distance_m"),
            heartbeat_seq=int(state.get("heartbeat_seq", 0)),
        )

    def next_seq(self) -> int:
        self.last_seq += 1
        return self.last_seq

    def make_message(self, msg_type: str, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
        return MessageEnvelope(
            msg_type=msg_type,
            sender_id=self.robot_id,
            seq=self.next_seq(),
            timestamp=time.time(),
            payload=payload or {},
        )

    def heartbeat(self) -> Dict[str, Any]:
        self.last_heartbeat = time.time()
        return {
            "robot_id": self.robot_id,
            "timestamp": self.last_heartbeat,
            "status": self.state.status,
            "battery": self.state.battery,
            "current_task_id": self.state.current_task_id,
            "current_node": self.state.current_node,
            "heartbeat_seq": self.last_seq,
        }

    def mark_failure(self, reason: str) -> None:
        self.failure_state = reason
        self.state.status = "FAULT"

    def local_decision_test(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = str(task.get("task_id"))
        self.add_task(task)
        bid = self.calculate_bid(task_id)
        return {
            "robot_id": self.robot_id,
            "task_id": task_id,
            "feasible": bid["feasible"],
            "estimated_cost": bid["estimated_cost"],
            "bid": bid["bid"],
            "status": self.state.status,
        }

    def may_enter_node(
        self,
        next_node: str,
        peer_requests: Optional[List[Dict[str, Any]]] = None,
        eta: float = 1.0,
        priority: Optional[str] = None,
    ) -> bool:
        """Evaluate if the agent is cleared to enter next_node based on neighbor states and arbitration."""
        if not next_node:
            return False

        # 1. Check neighbor occupancy / target via existing should_wait_for_neighbor
        for neighbor in self.neighbors.values():
            if self.should_wait_for_neighbor(neighbor, next_node):
                return False

        # 2. If conflicting peer requests exist for next_node, run existing arbitrate_intersection
        if peer_requests:
            prio = priority or "NORMAL"
            my_req = {
                "robot_id": self.robot_id,
                "priority": prio,
                "eta": float(eta),
                "intersection": next_node,
            }
            all_reqs = [my_req] + [r for r in peer_requests if r.get("robot_id") != self.robot_id]
            winner = EdgeRobotAgent.arbitrate_intersection(all_reqs)
            return winner == self.robot_id

        return True

    def run(self) -> None:
        """Simple independent agent loop for milestone validation."""
        self.state.status = "AVAILABLE"
        print(f"Edge agent {self.robot_id} started")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run a local edge robot agent.")
    parser.add_argument("--robot-id", default="R1")
    args = parser.parse_args()

    agent = EdgeRobotAgent(args.robot_id)
    agent.run()
