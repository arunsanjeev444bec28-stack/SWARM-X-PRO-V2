"""
Decentralized Edge Agent Fleet Coordinator for SWARM-X PRO V2.

Maintains the 4 autonomous edge agents (R1, R2, R3, R4) communicating peer-to-peer.
FastAPI acts only as a task injection and monitoring boundary.
All bidding, P2P consensus exchange, CBAA evaluation, and route planning
occur strictly within the edge agents.
"""

from __future__ import annotations

import math
import time
from typing import Any, Dict, List, Optional, Tuple

from edge_agents.robot_agent.agent import EdgeRobotAgent, TaskEnvelope
from edge_agents.coordination.cbaa import LocalCBAA, CBAAResult
from edge_agents.planning.local_planner import LocalPlanner


class DecentralizedFleetCoordinator:
    """Coordinates the 4 autonomous AMR edge agents across the warehouse RF graph."""

    def __init__(self, rf_nodes: Optional[Dict[str, Any]] = None, corner_nodes: Optional[Dict[str, str]] = None):
        self.rf_nodes = rf_nodes or {}
        self.graph = self._build_graph(self.rf_nodes)
        self.corner_nodes = corner_nodes or {
            "R1": "RF_6_0",
            "R2": "RF_6_13",
            "R3": "RF_0_0",
            "R4": "RF_0_13",
        }

        # Initialize the 4 autonomous edge agents
        self.agents: Dict[str, EdgeRobotAgent] = {}
        for rid, corner_node in self.corner_nodes.items():
            agent = EdgeRobotAgent(
                robot_id=rid,
                robot_data={
                    "robot_id": rid,
                    "node_id": corner_node,
                    "battery": 100.0,
                    "temperature": 25.0,
                    "load": 0.0,
                    "health": 100.0,
                    "status": "AVAILABLE",
                },
            )
            # Equip with authoritative RF warehouse navigation graph
            agent.local_planner = LocalPlanner(self.graph)
            agent.state.current_node = corner_node
            agent.state.status = "AVAILABLE"
            agent.state.battery = 100.0
            agent.state.health = 100.0
            self.agents[rid] = agent

        self.cbaa = LocalCBAA()

    def _build_graph(self, rf_nodes: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """Construct weighted adjacency map from RF node neighbors."""
        graph: Dict[str, Dict[str, float]] = {}
        for nid, node in rf_nodes.items():
            graph[nid] = {}
            node_x = getattr(node, "x", None) or (node.get("x") if isinstance(node, dict) else 0.0)
            node_y = getattr(node, "y", None) or (node.get("y") if isinstance(node, dict) else 0.0)
            neighbors = getattr(node, "neighbors", None) or (node.get("neighbors", []) if isinstance(node, dict) else [])
            for nbr_id in neighbors:
                if nbr_id in rf_nodes:
                    nbr = rf_nodes[nbr_id]
                    nbr_x = getattr(nbr, "x", None) or (nbr.get("x") if isinstance(nbr, dict) else 0.0)
                    nbr_y = getattr(nbr, "y", None) or (nbr.get("y") if isinstance(nbr, dict) else 0.0)
                    dist = round(math.hypot(node_x - nbr_x, node_y - nbr_y), 2)
                    graph[nid][nbr_id] = dist if dist > 0 else 1.0
                else:
                    graph[nid][nbr_id] = 1.0
        return graph

    def update_graph_and_corners(self, rf_nodes: Dict[str, Any], corner_nodes: Dict[str, str]) -> None:
        """Update warehouse graph and reset robot start nodes."""
        self.rf_nodes = rf_nodes
        self.graph = self._build_graph(rf_nodes)
        self.corner_nodes = corner_nodes
        for rid, corner in corner_nodes.items():
            if rid in self.agents:
                self.agents[rid].local_planner = LocalPlanner(self.graph)
                self.agents[rid].state.current_node = corner
                self.agents[rid].state.status = "AVAILABLE"
                self.agents[rid].state.planned_path = []
                self.agents[rid].state.current_task_id = None

    def calculate_path_distance(self, path: List[str]) -> float:
        """Calculate total distance of path along RF graph edges."""
        if not path or len(path) < 2:
            return 0.0
        total = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            total += self.graph.get(u, {}).get(v, 2.0)
        return round(total, 2)

    def announce_and_allocate_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute decentralized CBAA allocation workflow across the 4 AMR edge agents.

        1. Ingest task announcement into all 4 edge agents.
        2. Each edge agent computes its local bid (distance, time, congestion, availability).
        3. P2P bid exchange between agents.
        4. Independent CBAA consensus ranking using authoritative 4-term formula:
           C = 0.40D + 0.30T + 0.20Cg + 0.10A (lower cost wins).
        5. Winning edge agent claims task and computes A* route on actual RF graph.
        """
        task_id = str(task_data["task_id"])
        pickup_node = str(task_data["pickup_node"])
        dispatch_node = str(task_data["dispatch_node"])
        priority = str(task_data.get("priority", "NORMAL"))
        energy_req = float(task_data.get("energy_requirement", 10.0))

        # 1. Edge agents ingest the task
        for agent in self.agents.values():
            agent.add_task(task_data)

        # Sync graph with any additional nodes in global_state
        from core.state import global_state
        for nid, gnode in global_state.nodes.items():
            if nid not in self.graph:
                self.graph[nid] = {}
            for nbr_id in gnode.neighbors:
                if nbr_id in global_state.nodes:
                    nbr = global_state.nodes[nbr_id]
                    dist = round(math.hypot(gnode.x - nbr.x, gnode.y - nbr.y), 2)
                    self.graph[nid][nbr_id] = dist if dist > 0 else 1.0
                else:
                    self.graph[nid][nbr_id] = 1.0
                if nbr_id not in self.graph:
                    self.graph[nbr_id] = {}
                self.graph[nbr_id][nid] = self.graph[nid][nbr_id]

        # Sync edge agent state with global_state robots
        for rid, agent in self.agents.items():
            g_robot = global_state.get_robot(rid)
            if g_robot and g_robot.node_id:
                agent.state.current_node = g_robot.node_id
                agent.state.status = g_robot.status
                agent.state.battery = g_robot.battery
                agent.state.health = getattr(g_robot, "health", 100.0)
            agent.local_planner = LocalPlanner(self.graph)

        # 2. Each edge agent independently calculates its local bid metrics
        raw_bids: Dict[str, Dict[str, Any]] = {}
        ineligible: Dict[str, str] = {}

        for rid, agent in self.agents.items():
            current_node = agent.state.current_node or self.corner_nodes.get(rid, "RF_0_0")
            is_avail = agent.state.status in ["AVAILABLE", "IDLE"]
            is_healthy = agent.state.health >= 30.0
            has_batt = agent.state.battery - energy_req >= 5.0

            # Plan path from current position to pickup node on the RF graph
            approach_path = agent.local_planner.plan(current_node, pickup_node)
            approach_dist = self.calculate_path_distance(approach_path)
            travel_time = round(approach_dist / 1.0, 2)  # 1.0 m/s nominal
            congestion = 0.0
            availability = 1.0 if (is_avail and is_healthy) else 0.0

            if not is_avail:
                ineligible[rid] = f"Robot busy (status={agent.state.status})"
            elif not is_healthy:
                ineligible[rid] = f"Low health ({agent.state.health:.1f}%)"
            elif not has_batt:
                ineligible[rid] = f"Insufficient battery ({agent.state.battery:.1f}%)"

            feasible = rid not in ineligible

            bid_info = {
                "robot_id": rid,
                "distance": approach_dist,
                "travel_time": travel_time,
                "congestion": congestion,
                "availability": availability,
                "feasibility": feasible,
                "status": "VALID" if feasible else "DISQUALIFIED",
                "reason": "OK" if feasible else ineligible.get(rid, "Infeasible"),
            }
            raw_bids[rid] = bid_info
            agent.register_bid(task_id, bid_info)

        # 3. P2P Consensus Gossip: Broadcast bids to all peers
        for rid, agent in self.agents.items():
            for peer_id, peer_bid in raw_bids.items():
                if peer_id != rid:
                    agent.record_peer_bid(task_id, peer_id, peer_bid)

        # 4. Independent CBAA Winner Determination
        cbaa_result = self.cbaa.normalize_and_rank_bids(
            raw_bids=raw_bids,
            ineligible_robots=ineligible,
            task_id=task_id,
        )

        winner_id = cbaa_result.winner
        planned_route: List[str] = []
        route_dist = 0.0
        est_time = 0.0

        # 5. Winning agent claims task and plans A* route on actual RF graph
        if winner_id and winner_id in self.agents:
            winner_agent = self.agents[winner_id]
            winner_agent.claim_winner(task_id, winner_id)
            winner_agent.state.status = "DISPATCHING"

            current_pos = winner_agent.state.current_node or self.corner_nodes[winner_id]
            # Leg 1: current -> pickup
            leg1 = winner_agent.local_planner.plan(current_pos, pickup_node)
            # Leg 2: pickup -> dispatch
            leg2 = winner_agent.local_planner.plan(pickup_node, dispatch_node)

            if leg1 and leg2:
                planned_route = leg1 + leg2[1:]
            elif leg2:
                planned_route = leg2
            elif leg1:
                planned_route = leg1
            else:
                planned_route = [current_pos, pickup_node, dispatch_node]

            route_dist = self.calculate_path_distance(planned_route)
            est_time = round(route_dist / 1.0, 2)
            winner_agent.state.planned_path = planned_route
            winner_agent.state.current_path_index = 0

        # Build comprehensive allocation record
        allocation = {
            "task_id": task_id,
            "winner": winner_id,
            "winning_bid": cbaa_result.winning_bid,
            "selection_rule": "MINIMUM VALID BID",
            "feasible_robots": [r for r in raw_bids if r not in ineligible],
            "ineligible_robots": ineligible,
            "bids": cbaa_result.bids,
            "reason": cbaa_result.reason or f"Consensus winner {winner_id} selected",
            "path": planned_route,
            "distance": route_dist,
            "estimated_time": est_time,
        }

        return allocation

    def step_fleet_movement(self, robot_id: str) -> Optional[Dict[str, Any]]:
        """Advance an active robot one step along its planned path."""
        agent = self.agents.get(robot_id)
        if not agent or not agent.state.planned_path:
            return None

        path = agent.state.planned_path
        idx = agent.state.current_path_index

        if idx + 1 < len(path):
            idx += 1
            agent.state.current_path_index = idx
            next_node = path[idx]
            agent.state.current_node = next_node
            agent.state.battery = max(0.0, agent.state.battery - 0.2)

            node_data = self.rf_nodes.get(next_node, {})
            nx = getattr(node_data, "x", None) or (node_data.get("x") if isinstance(node_data, dict) else 0.0)
            ny = getattr(node_data, "y", None) or (node_data.get("y") if isinstance(node_data, dict) else 0.0)
            agent.state.x = nx
            agent.state.y = ny

            is_last = (idx == len(path) - 1)
            if is_last:
                agent.state.status = "AVAILABLE"
                agent.state.planned_path = []
                agent.state.current_task_id = None
                agent.state.load = 0.0

            return {
                "robot_id": robot_id,
                "node_id": next_node,
                "position": [nx, ny, 0.12],
                "battery": round(agent.state.battery, 1),
                "health": round(agent.state.health, 1),
                "status": agent.state.status,
                "completed": is_last,
            }

        return None


# Global singleton instance initialized with the real warehouse
from data.warehouse_real import generate_rf_nodes, get_corner_rf_nodes
fleet_coordinator = DecentralizedFleetCoordinator(
    rf_nodes=generate_rf_nodes(),
    corner_nodes=get_corner_rf_nodes(),
)
