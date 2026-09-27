from __future__ import annotations

from typing import Any, Dict, List, Optional
from edge_agents.robot_agent.agent import EdgeRobotAgent, TaskEnvelope


def may_enter_node(
    agent: EdgeRobotAgent,
    next_node: str,
    peer_requests: Optional[List[Dict[str, Any]]] = None,
    eta: float = 1.0,
    priority: Optional[str] = None,
) -> bool:
    """Evaluate if agent may enter next_node using its internal arbitration rules."""
    return agent.may_enter_node(next_node, peer_requests=peer_requests, eta=eta, priority=priority)


__all__ = ["EdgeRobotAgent", "TaskEnvelope", "may_enter_node"]
