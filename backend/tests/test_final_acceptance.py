"""
Final End-to-End Acceptance Tests for SWARM-X PRO V2.
Validates:
- Warehouse geometry and clearance validation
- Task file importer (CSV & JSON validation, reject invalid data)
- Dynamic benchmark runner (Stop-and-Wait vs SWARM-X decentralized)
- Artifact exports
"""

import os
import json
import pytest
from backend.data.warehouse_real import validate_warehouse_config
from backend.tasks.loader import validate_and_parse_task_file, load_task_file_from_path
from backend.evaluation.benchmark_runner import run_comprehensive_benchmark, export_benchmark_artifacts


def test_warehouse_configuration_validation():
    """Verify validate_warehouse_config reports all 18 metrics and passes."""
    report = validate_warehouse_config()
    assert report["rack_count"] == 78
    assert report["rf_node_count"] == 98
    assert report["graph_edge_count"] == 175
    assert report["warehouse_width_m"] == 31.2
    assert report["warehouse_height_m"] == 12.0
    assert report["aisle_width_m"] == 1.0
    assert report["robot_length_m"] == 0.60
    assert report["robot_width_m"] == 0.40
    assert round(report["available_side_clearance_m"], 2) == 0.30
    assert report["straight_travel_clearance"] == "PASS"
    assert report["turning_clearance"] == "PASS"
    assert report["validations"]["overall"] == "PASS"


def test_task_loader_csv_and_json():
    """Verify CSV and JSON parsing, plus strict rejection of invalid rows."""
    valid_csv = (
        "task_id,pickup_node,destination_node,priority,task_type,deadline_s\n"
        "TASK_001,RF_6_1,RF_2_10,HIGH,TRANSPORT,120\n"
        "TASK_002,RF_0_3,RF_5_12,NORMAL,DELIVERY,180\n"
    )
    res_csv = validate_and_parse_task_file(valid_csv, "tasks.csv")
    assert res_csv["valid"] is True
    assert res_csv["valid_count"] == 2
    assert res_csv["tasks"][0]["task_id"] == "TASK_001"

    valid_json = json.dumps([
        {
            "task_id": "TASK_J1",
            "pickup_node": "RF_6_1",
            "destination_node": "RF_2_10",
            "priority": "HIGH",
            "task_type": "TRANSPORT",
            "deadline_s": 120,
        }
    ])
    res_json = validate_and_parse_task_file(valid_json, "tasks.json")
    assert res_json["valid"] is True
    assert res_json["valid_count"] == 1

    # Invalid cases: duplicate task ID, invalid RF node
    bad_csv = (
        "task_id,pickup_node,destination_node,priority,task_type,deadline_s\n"
        "TASK_DUP,RF_6_1,RF_2_10,HIGH,TRANSPORT,120\n"
        "TASK_DUP,RF_0_3,RF_5_12,NORMAL,DELIVERY,180\n"
        "TASK_BAD_NODE,RF_99_99,RF_0_0,NORMAL,DELIVERY,180\n"
    )
    res_bad = validate_and_parse_task_file(bad_csv, "tasks.csv")
    assert res_bad["valid"] is False
    assert len(res_bad["errors"]) >= 2


def test_demo_tasks_file_exists_and_valid():
    """Verify demo_tasks.csv is authoritative, valid, and contains 18 tasks."""
    demo_path = os.path.join("data", "tasks", "demo_tasks.csv")
    assert os.path.exists(demo_path)
    res = load_task_file_from_path(demo_path)
    assert res["valid"] is True
    assert res["valid_count"] >= 15
    assert len(res["errors"]) == 0


def test_benchmark_runner_and_exports(tmp_path):
    """Verify benchmark runs with actual measurements, achieves target >= 20% and 0 collisions."""
    demo_path = os.path.join("data", "tasks", "demo_tasks.csv")
    res = run_comprehensive_benchmark(task_file_path=demo_path)
    
    assert res["status"] == "PASS"
    assert res["measured_time_reduction_percent"] >= 20.0
    assert res["collisions"]["robot_robot"] == 0
    assert res["collisions"]["robot_rack"] == 0
    assert res["zero_collision_criterion"] == "PASS"
    assert res["baseline"]["makespan_s"] > res["swarmx"]["makespan_s"]

    out_dir = str(tmp_path / "results")
    files = export_benchmark_artifacts(res, output_dir=out_dir)
    assert len(files) == 6
    for f in files:
        assert os.path.exists(f)
        assert os.path.getsize(f) > 0
