import pytest
import math
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from api.main import app
from core.state import global_state
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from simulation.engine import simulator
from data.warehouse_real import (
    generate_78_racks,
    generate_rf_nodes,
    generate_nav_edges,
    get_corner_rf_nodes,
    generate_warehouse_model,
    init_real_warehouse_state,
    TOTAL_RACKS,
    TOTAL_RF_NODES,
    GRID_COLS,
    GRID_ROWS,
    AISLE_COLS,
    AISLE_ROWS,
)
from edge_agents.fleet_coordinator import fleet_coordinator

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.reset()
    simulator.is_running = False
    simulator.current_time_step = 0
    init_real_warehouse_state(global_state)


def test_warehouse_78_racks_and_98_rf_nodes():
    """Verify exactly 78 racks (13x6) and 98 RF intersection nodes (14x7)."""
    racks = generate_78_racks()
    assert len(racks) == 78, f"Expected exactly 78 racks, got {len(racks)}"
    assert GRID_COLS * GRID_ROWS == 78

    nodes = generate_rf_nodes()
    assert len(nodes) == 98, f"Expected 98 RF intersection nodes, got {len(nodes)}"
    assert AISLE_COLS * AISLE_ROWS == 98

    # Check rack IDs
    rack_ids = [r.rack_id for r in racks]
    assert len(set(rack_ids)) == 78
    assert "RACK_01" in rack_ids
    assert "RACK_78" in rack_ids

    # Check RF intersection nodes are orthogonal (no diagonals)
    edges = generate_nav_edges(nodes)
    assert len(edges) > 0
    for edge in edges:
        # Distance should match orthogonal spacing (2.4m X or 2.0m Y)
        assert math.isclose(edge.distance, 2.4, rel_tol=1e-2) or math.isclose(edge.distance, 2.0, rel_tol=1e-2), (
            f"Edge {edge.from_node}->{edge.to_node} distance {edge.distance} must be strictly orthogonal"
        )


def test_corner_amr_positions_and_initial_availability():
    """Verify 4 AMRs are at the four valid corner RF nodes and initially AVAILABLE."""
    nodes = generate_rf_nodes()
    corners = get_corner_rf_nodes(nodes)

    assert len(corners) == 4
    assert corners["R1"] == "RF_6_0"   # Top-left (max Y, min X)
    assert corners["R2"] == "RF_6_13"  # Top-right (max Y, max X)
    assert corners["R3"] == "RF_0_0"   # Bottom-left (min Y, min X)
    assert corners["R4"] == "RF_0_13"  # Bottom-right (min Y, max X)

    # In global_state initialized by startup/fixture
    robots = {r.robot_id: r for r in global_state.get_all_robots()}
    assert len(robots) == 4
    for rid in ["R1", "R2", "R3", "R4"]:
        assert rid in robots
        assert robots[rid].node_id == corners[rid]
        assert robots[rid].status in ["AVAILABLE", "IDLE"]
        assert robots[rid].battery == 100.0

    # Zero tasks, zero fake missions, zero fake failures
    assert len(global_state.tasks) == 0
    assert len(global_state.allocations) == 0
    assert len(global_state.failures) == 0


def test_api_warehouse_model_endpoint():
    """Verify GET /api/warehouse returns full 78-rack model."""
    resp = client.get("/api/warehouse")
    assert resp.status_code == 200
    data = resp.json()

    assert data["rack_count"] == 78
    assert data["rf_node_count"] == 98
    assert len(data["racks"]) == 78
    assert len(data["rf_nodes"]) == 98
    assert len(data["edges"]) > 0
    assert "corner_nodes" in data
    assert data["corner_nodes"]["R1"] == "RF_6_0"


def test_decentralized_cbaa_allocation_and_route():
    """Verify decentralized task allocation selects closest corner AMR and plans route on RF graph."""
    # Create task near top-left: pickup at RF_5_1, dispatch at RF_3_6
    task_payload = {
        "task_id": "TASK_TEST_01",
        "pickup_node": "RF_5_1",
        "dispatch_node": "RF_3_6",
        "priority": "HIGH",
        "task_type": "TRANSPORT",
        "energy_requirement": 5.0,
    }

    resp = client.post("/api/tasks", json=task_payload)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["task_id"] == "TASK_TEST_01"

    # R1 is at RF_6_0, which is right next to RF_5_1 (1 step away)
    # R2 is at RF_6_13, R3 is at RF_0_0, R4 is at RF_0_13
    # R1 must win the decentralized CBAA bid
    assert res_data["winner"] == "R1"
    assert len(res_data["bids"]) == 4

    # Check bids do not contain energy or workload
    r1_bid = res_data["bids"]["R1"]
    assert "distance" in r1_bid
    assert "energy" not in r1_bid
    assert "workload" not in r1_bid

    # Route must exist and start from R1's position RF_6_0
    route = res_data["path"]
    assert len(route) >= 3
    assert route[0] == "RF_6_0"
    assert "RF_5_1" in route
    assert route[-1] == "RF_3_6"

    # Verify all hops are valid edges in the RF graph (no diagonals)
    nodes = generate_rf_nodes()
    for i in range(len(route) - 1):
        u, v = route[i], route[i + 1]
        assert v in nodes[u].neighbors, f"Hop {u}->{v} must be a valid RF aisle edge"
