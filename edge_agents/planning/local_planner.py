from __future__ import annotations

import heapq
import math
from typing import Any, Dict, Iterable, List, Optional


class LocalPlanner:
    """Deterministic A* planner for edge-local route computation.

    This intentionally stays additive to the backend system and reuses the same
    graph-search pattern as the existing warehouse planner without replacing it.
    """

    def __init__(self, graph: Optional[Dict[str, Any]] = None, cost_weights: Optional[Dict[str, float]] = None):
        self.graph = self._normalise_graph(graph or {})
        self.cost_weights = {
            "distance": 1.0,
            "turning": 0.35,
            "congestion": 0.25,
            "restricted": 30.0,
            "obstacle": 1000.0,
            **(cost_weights or {}),
        }

    @staticmethod
    def _normalise_graph(graph: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        normalised: Dict[str, Dict[str, float]] = {}
        for node, neighbours in (graph or {}).items():
            if isinstance(neighbours, dict):
                normalised[str(node)] = {str(key): float(value) for key, value in neighbours.items()}
            elif isinstance(neighbours, Iterable):
                normalised[str(node)] = {str(neighbour): 1.0 for neighbour in neighbours}
            else:
                normalised[str(node)] = {}
        return normalised

    def _heuristic(self, node: str, goal: str) -> float:
        if node == goal:
            return 0.0
        return 1.0

    def _edge_cost(self, node: str, next_node: str, prev_node: Optional[str] = None, blocked: Optional[set[str]] = None) -> float:
        if blocked and next_node in blocked:
            return math.inf
        base_cost = float(self.graph.get(node, {}).get(next_node, 1.0))
        if prev_node and node != prev_node:
            # Small deterministic turning penalty for route smoothness.
            return base_cost + self.cost_weights["turning"]
        return base_cost

    def plan(
        self,
        start: str,
        goal: str,
        graph: Optional[Dict[str, Any]] = None,
        blocked: Optional[set[str]] = None,
        prev_node: Optional[str] = None,
    ) -> List[str]:
        if not start or not goal:
            return []
        if start == goal:
            return [start]

        active_graph = self._normalise_graph(graph or self.graph)
        if start not in active_graph and goal not in active_graph:
            return []

        open_heap: List[tuple[float, float, str, List[str], Optional[str]]] = []
        heapq.heappush(open_heap, (self._heuristic(start, goal), 0.0, start, [start], prev_node))
        best_cost = {start: 0.0}
        visited: set[str] = set()

        while open_heap:
            _, g_cost, node, path, last_node = heapq.heappop(open_heap)
            if node in visited:
                continue
            visited.add(node)
            if node == goal:
                return path
            for neighbour, weight in active_graph.get(node, {}).items():
                if blocked and neighbour in blocked:
                    continue
                cost = self._edge_cost(node, neighbour, prev_node=last_node, blocked=blocked)
                if not math.isfinite(cost):
                    continue
                next_cost = g_cost + (weight * self.cost_weights["distance"]) + cost
                if next_cost < best_cost.get(neighbour, math.inf):
                    best_cost[neighbour] = next_cost
                    heapq.heappush(
                        open_heap,
                        (
                            next_cost + self._heuristic(neighbour, goal),
                            next_cost,
                            neighbour,
                            path + [neighbour],
                            node,
                        ),
                    )

        fallback = []
        if start in active_graph and goal in active_graph.get(start, {}):
            fallback = [start, goal]
        return fallback
