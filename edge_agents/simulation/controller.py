from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from edge_agents.common.state import NeighborState
from edge_agents.robot_agent.agent import EdgeRobotAgent


class NodeArbitrationController:
    """Thread-safe node-level arbitration controller connecting EdgeRobotAgent and CoppeliaSimMotionBridge.

    Enforces:
    - Atomic node occupancy registry (RF node -> robot ID) in integration layer only.
    - Physical safety invariant: strictly no two robots occupying the same RF node simultaneously.
    - Delegation to existing EdgeRobotAgent arbitration (arbitrate_intersection, should_wait_for_neighbor).
    - Structured event logging for INTENT, ARBITRATION, WAIT, ENTER_NODE, EXIT_NODE.
    """

    def __init__(self, agents: Optional[Dict[str, EdgeRobotAgent]] = None) -> None:
        self.agents: Dict[str, EdgeRobotAgent] = dict(agents or {})
        self.occupancy: Dict[str, str] = {}  # node_id -> robot_id
        self.intents: Dict[str, Dict[str, Any]] = {}  # robot_id -> intent_payload
        self.priorities: Dict[str, str] = {}  # robot_id -> priority string
        self.event_log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def set_priority(self, robot_id: str, priority: str) -> None:
        with self._lock:
            self.priorities[robot_id] = str(priority).upper()

    def register_agent(self, agent: EdgeRobotAgent, initial_node: Optional[str] = None) -> None:
        with self._lock:
            self.agents[agent.robot_id] = agent
            start_node = initial_node or agent.state.current_node
            if start_node:
                self.occupancy[start_node] = agent.robot_id
                agent.state.current_node = start_node

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        entry = {
            "timestamp": time.time(),
            "event": event_type,
            **payload,
        }
        self.event_log.append(entry)

    def register_intent(
        self,
        robot_id: str,
        current_node: str,
        next_node: str,
        eta: float = 1.0,
        priority: Optional[str] = None,
        planned_path: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Announce intent for an upcoming node so peers/arbitration can evaluate contention."""
        with self._lock:
            agent = self.agents.get(robot_id)
            if agent is None:
                agent = EdgeRobotAgent(robot_id)
                self.agents[robot_id] = agent

            prio = (
                priority
                or self.priorities.get(robot_id)
                or getattr(agent.state, "priority", None)
                or agent.robot_data.get("priority", "NORMAL")
            )
            intent = agent.build_intent(
                task_id=f"TASK_{robot_id}",
                current_node=current_node,
                next_node=next_node,
                planned_path=planned_path,
                eta=float(eta),
                priority=prio,
            )
            self.intents[robot_id] = intent["payload"]
            self.log_event("INTENT", {
                "robot_id": robot_id,
                "current_node": current_node,
                "next_node": next_node,
                "priority": prio,
                "eta": float(eta),
            })
            return intent["payload"]

    def can_enter_node(
        self,
        robot_id: str,
        current_node: str,
        next_node: str,
        eta: float = 1.0,
        priority: Optional[str] = None,
    ) -> bool:
        """Arbitration gatekeeper queried before moving from current_node into next_node."""
        with self._lock:
            agent = self.agents.get(robot_id)
            if agent is None:
                agent = EdgeRobotAgent(robot_id)
                self.agents[robot_id] = agent

            # Invariant check: is next_node already occupied by another robot?
            occupant = self.occupancy.get(next_node)
            if occupant is not None and occupant != robot_id:
                self.log_event("WAIT", {
                    "robot_id": robot_id,
                    "current_node": current_node,
                    "next_node": next_node,
                    "reason": f"Node occupied by {occupant}",
                })
                return False

            # Resolve effective priority and path
            existing_intent = self.intents.get(robot_id, {})
            prio = (
                priority
                or self.priorities.get(robot_id)
                or existing_intent.get("priority")
                or getattr(agent.state, "priority", None)
                or agent.robot_data.get("priority", "NORMAL")
            )
            planned_path = existing_intent.get("planned_path")

            # Update INTENT for robot_id
            intent = agent.build_intent(
                task_id=f"TASK_{robot_id}",
                current_node=current_node,
                next_node=next_node,
                planned_path=planned_path,
                eta=float(eta),
                priority=prio,
            )
            self.intents[robot_id] = intent["payload"]
            self.log_event("INTENT", {
                "robot_id": robot_id,
                "current_node": current_node,
                "next_node": next_node,
                "priority": prio,
                "eta": float(eta),
            })

            # Check if peer robots are also contending for next_node
            peer_reqs: List[Dict[str, Any]] = []
            for other_id, other_intent in self.intents.items():
                if other_id != robot_id:
                    other_next = other_intent.get("next_node")
                    other_path = other_intent.get("planned_path", [])
                    if other_next == next_node or (next_node in other_path and other_intent.get("current_node") != next_node):
                        peer_reqs.append({
                            "robot_id": other_id,
                            "priority": other_intent.get("priority", self.priorities.get(other_id, "NORMAL")),
                            "eta": float(other_intent.get("eta", 1.0)),
                            "intersection": next_node,
                        })

            # If contested, run EdgeRobotAgent arbitration
            if peer_reqs:
                cleared = agent.may_enter_node(next_node, peer_requests=peer_reqs, eta=eta, priority=prio)
                all_candidates = [robot_id] + [r["robot_id"] for r in peer_reqs]
                all_reqs = [{
                    "robot_id": robot_id,
                    "priority": prio,
                    "eta": float(eta),
                    "intersection": next_node,
                }] + peer_reqs
                winner = EdgeRobotAgent.arbitrate_intersection(all_reqs)
                self.log_event("ARBITRATION", {
                    "intersection": next_node,
                    "candidates": all_candidates,
                    "winner": winner,
                    "cleared": cleared,
                })
                if not cleared:
                    self.log_event("WAIT", {
                        "robot_id": robot_id,
                        "current_node": current_node,
                        "next_node": next_node,
                        "reason": f"Yielding to winner {winner}",
                    })
                    return False

            # Permission granted: claim next_node in occupancy registry
            self.occupancy[next_node] = robot_id
            self.log_event("ENTER_NODE", {
                "robot_id": robot_id,
                "node_id": next_node,
                "from_node": current_node,
            })
            return True

    def on_node_reached(self, robot_id: str, previous_node: str, current_node: str) -> None:
        """Invoked when physical movement to current_node is completed."""
        with self._lock:
            # Release previous node occupancy
            if self.occupancy.get(previous_node) == robot_id:
                del self.occupancy[previous_node]
                self.log_event("EXIT_NODE", {
                    "robot_id": robot_id,
                    "node_id": previous_node,
                })

            # Update agent state
            agent = self.agents.get(robot_id)
            if agent:
                agent.state.current_node = current_node

            # Clear intent for the completed node
            if robot_id in self.intents and self.intents[robot_id].get("next_node") == current_node:
                del self.intents[robot_id]
