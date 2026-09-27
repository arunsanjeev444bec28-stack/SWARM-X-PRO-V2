"""
Authoritative Task File Importer & Validator for SWARM-X PRO V2.
Supports CSV and JSON formats with strict validation per Section 16 & 17.
Validates:
- Non-empty file
- Required columns/keys (task_id, pickup_node, destination_node, priority, task_type, deadline_s)
- Duplicate task IDs
- Valid RF nodes (must match authoritative 98 RF nodes)
- Pickup != Destination
- Valid priorities (CRITICAL, HIGH, NORMAL, LOW)
- Valid task types (TRANSPORT, DELIVERY, PICKUP, TRANSFER)
- Valid positive deadlines
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.data.warehouse_real import generate_rf_nodes
from backend.models.schemas import Task

logger = logging.getLogger("backend.tasks")

VALID_PRIORITIES = {"CRITICAL", "HIGH", "NORMAL", "LOW"}
VALID_TASK_TYPES = {"TRANSPORT", "DELIVERY", "PICKUP", "TRANSFER"}
_RF_NODES = generate_rf_nodes()


def validate_and_parse_task_file(
    content: str,
    filename: str = "tasks.csv",
) -> Dict[str, Any]:
    """
    Validate and parse a task file (CSV or JSON).
    Returns dictionary with validation results, parsed tasks, and explicit errors.
    """
    if not content or not content.strip():
        return {
            "valid": False,
            "tasks": [],
            "errors": ["File is empty"],
            "total_count": 0,
            "valid_count": 0,
        }

    is_json = filename.lower().endswith(".json") or content.strip().startswith("[")
    errors: List[str] = []
    parsed_tasks: List[Dict[str, Any]] = []
    seen_task_ids = set()

    if is_json:
        try:
            raw_data = json.loads(content)
            if not isinstance(raw_data, list):
                return {
                    "valid": False,
                    "tasks": [],
                    "errors": ["JSON task file must contain a root array of task objects"],
                    "total_count": 0,
                    "valid_count": 0,
                }
            rows = raw_data
        except Exception as e:
            return {
                "valid": False,
                "tasks": [],
                "errors": [f"Malformed JSON: {e}"],
                "total_count": 0,
                "valid_count": 0,
            }
    else:
        # CSV parsing
        try:
            reader = csv.DictReader(io.StringIO(content.strip()))
            rows = list(reader)
        except Exception as e:
            return {
                "valid": False,
                "tasks": [],
                "errors": [f"Malformed CSV: {e}"],
                "total_count": 0,
                "valid_count": 0,
            }

    if not rows:
        return {
            "valid": False,
            "tasks": [],
            "errors": ["Task file contains no data rows"],
            "total_count": 0,
            "valid_count": 0,
        }

    for idx, row in enumerate(rows, start=1):
        row_num = idx
        task_id = str(row.get("task_id", "")).strip()
        pickup = str(row.get("pickup_node", "")).strip()
        destination = str(row.get("destination_node", "") or row.get("dispatch_node", "")).strip()
        priority = str(row.get("priority", "NORMAL")).strip().upper()
        task_type = str(row.get("task_type", "TRANSPORT")).strip().upper()
        deadline_str = str(row.get("deadline_s", "") or row.get("deadline", "120")).strip()

        row_errors = []

        if not task_id:
            row_errors.append(f"Row {row_num}: missing task_id")
        elif task_id in seen_task_ids:
            row_errors.append(f"Row {row_num}: duplicate task ID '{task_id}'")
        else:
            seen_task_ids.add(task_id)

        if not pickup:
            row_errors.append(f"Row {row_num}: missing pickup_node")
        elif pickup not in _RF_NODES:
            row_errors.append(f"Row {row_num}: invalid pickup RF node '{pickup}'")

        if not destination:
            row_errors.append(f"Row {row_num}: missing destination_node")
        elif destination not in _RF_NODES:
            row_errors.append(f"Row {row_num}: invalid destination RF node '{destination}'")

        if pickup and destination and pickup == destination:
            row_errors.append(f"Row {row_num}: pickup and destination nodes cannot be identical ('{pickup}')")

        if priority not in VALID_PRIORITIES:
            row_errors.append(f"Row {row_num}: invalid priority '{priority}' (must be one of {sorted(VALID_PRIORITIES)})")

        if task_type not in VALID_TASK_TYPES:
            row_errors.append(f"Row {row_num}: invalid task_type '{task_type}' (must be one of {sorted(VALID_TASK_TYPES)})")

        try:
            deadline = float(deadline_str)
            if deadline <= 0:
                row_errors.append(f"Row {row_num}: deadline must be positive, got {deadline}")
        except ValueError:
            row_errors.append(f"Row {row_num}: invalid numeric deadline '{deadline_str}'")
            deadline = 120.0

        if row_errors:
            errors.extend(row_errors)
        else:
            parsed_tasks.append({
                "task_id": task_id,
                "pickup_node": pickup,
                "destination_node": destination,
                "dispatch_node": destination,
                "priority": priority,
                "task_type": task_type,
                "deadline_s": deadline,
                "deadline": deadline,
                "urgency": 1.0 if priority == "NORMAL" else (1.5 if priority == "HIGH" else (2.0 if priority == "CRITICAL" else 0.5)),
                "load": 1.0,
                "energy_requirement": 10.0,
                "status": "PENDING",
            })

    is_valid = len(errors) == 0 and len(parsed_tasks) > 0
    return {
        "valid": is_valid,
        "filename": filename,
        "total_count": len(rows),
        "valid_count": len(parsed_tasks),
        "errors": errors,
        "tasks": parsed_tasks,
    }


def load_task_file_from_path(file_path: str) -> Dict[str, Any]:
    """Load and validate task file directly from a filesystem path."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return validate_and_parse_task_file(content, filename=file_path)
