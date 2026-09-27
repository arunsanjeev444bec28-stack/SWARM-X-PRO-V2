"""Adapters that bridge the existing backend models to the edge-agent layer.

These adapters intentionally do not rewrite or replace the existing backend
schemas. They provide a narrow compatibility layer used by robot agents.
"""

from __future__ import annotations

from typing import Any, Dict


def adapt_robot_payload(robot: Any) -> Dict[str, Any]:
    """Return a minimal dict-like shape for robot state inside edge agents."""
    return {
        "robot_id": getattr(robot, "robot_id", None),
        "node_id": getattr(robot, "node_id", None),
        "battery": getattr(robot, "battery", 100.0),
        "temperature": getattr(robot, "temperature", 25.0),
        "load": getattr(robot, "load", 0.0),
        "health": getattr(robot, "health", 100.0),
        "status": getattr(robot, "status", "IDLE"),
    }


def adapt_task_payload(task: Any) -> Dict[str, Any]:
    """Return a minimal dict-like shape for task state inside edge agents."""
    return {
        "task_id": getattr(task, "task_id", None),
        "pickup_node": getattr(task, "pickup_node", None),
        "dispatch_node": getattr(task, "dispatch_node", None),
        "priority": getattr(task, "priority", "NORMAL"),
        "urgency": getattr(task, "urgency", 1.0),
        "deadline": getattr(task, "deadline", 100.0),
        "load": getattr(task, "load", 1.0),
        "energy_requirement": getattr(task, "energy_requirement", 10.0),
    }
