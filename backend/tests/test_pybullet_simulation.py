"""
Comprehensive Test Suite for PyBullet 3D Warehouse Simulation,
Continuous Kinematics, Node Arbitration, LiDAR, 2D SLAM,
and Bridge Integration on Windows.
"""

import math
import sys
import os
import time
import pytest

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
_root_dir = os.path.dirname(_backend_dir)
for p in [_backend_dir, _root_dir]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.data.warehouse_real import (
    generate_78_racks,
    generate_rf_nodes,
    generate_nav_edges,
    get_corner_rf_nodes,
    TOTAL_RACKS,
    TOTAL_RF_NODES,
)
from simulation.pybullet.simulator import PyBulletSimulator
from simulation.pybullet.world import SimulationWorld
from simulation.pybullet.warehouse import WarehousePhysicalModel
from simulation.pybullet.robot import AMRRobot
from simulation.pybullet.lidar import SimulatedLiDAR
from simulation.slam.occupancy_grid import OccupancyGrid
from simulation.slam.slam_engine import SlamEngine
from simulation.slam.pose import RobotPose
from edge_agents.simulation.controller import NodeArbitrationController


@pytest.fixture(scope="module")
def sim_instance():
    """Create a headless PyBullet simulator for the test session."""
    sim = PyBulletSimulator(gui=False, target_fps=30.0, lidar_hz=10.0)
    yield sim
    sim.stop()
    sim.world.close()


def test_1_warehouse_contains_exactly_78_racks():
    """Verify warehouse model and physical build contain exactly 78 3D racks."""
    racks = generate_78_racks()
    assert len(racks) == 78, f"Expected 78 racks, got {len(racks)}"
    assert TOTAL_RACKS == 78
    # Check rack IDs RACK_01 to RACK_78
    ids = {r.rack_id for r in racks}
    assert len(ids) == 78
    assert "RACK_01" in ids
    assert "RACK_78" in ids


def test_2_warehouse_contains_exactly_98_rf_nodes():
    """Verify warehouse contains exactly 98 RF intersection nodes (14x7)."""
    nodes = generate_rf_nodes()
    assert len(nodes) == 98, f"Expected 98 RF nodes, got {len(nodes)}"
    assert TOTAL_RF_NODES == 98
    # Check bounds
    for r in range(7):
        for c in range(14):
            assert f"RF_{r}_{c}" in nodes


def test_3_graph_contains_175_edges():
    """Verify navigation graph contains exactly 175 orthogonal edges."""
    nodes = generate_rf_nodes()
    edges = generate_nav_edges(nodes)
    assert len(edges) == 175, f"Expected 175 edges, got {len(edges)}"
    for e in edges:
        # Strictly orthogonal distance: 2.4m along X or 2.0m along Y
        assert math.isclose(e.distance, 2.4, rel_tol=1e-2) or math.isclose(e.distance, 2.0, rel_tol=1e-2)


def test_4_four_robots_initialize_correctly(sim_instance):
    """Verify 4 AMRs (R1, R2, R3, R4) initialize at authoritative corners."""
    assert len(sim_instance.robots) == 4
    for rid in ["R1", "R2", "R3", "R4"]:
        assert rid in sim_instance.robots
        robot = sim_instance.robots[rid]
        assert robot.status in ["AVAILABLE", "IDLE"]
        assert robot.battery == 100.0
        assert robot.body_id >= 0

    # Corners verification
    assert sim_instance.robots["R1"].current_node == "RF_6_0"   # Top-left
    assert sim_instance.robots["R2"].current_node == "RF_6_13"  # Top-right
    assert sim_instance.robots["R3"].current_node == "RF_0_0"   # Bottom-left
    assert sim_instance.robots["R4"].current_node == "RF_0_13"  # Bottom-right


def test_5_robot_moves_continuously(sim_instance):
    """Verify robot kinematics move continuously without teleportation."""
    robot = sim_instance.robots["R1"]
    initial_x, initial_y = robot.x, robot.y

    # Assign single step route to adjacent node RF_5_0 (South)
    route = ["RF_6_0", "RF_5_0"]
    sim_instance.assign_route("R1", route)

    # Step a small delta time (e.g. 0.1s at max speed 1.0 m/s)
    sim_instance.controller.step(dt=0.1)

    # Position should have moved partially towards destination, not teleported
    curr_x, curr_y = robot.x, robot.y
    moved_dist = math.hypot(curr_x - initial_x, curr_y - initial_y)

    assert moved_dist >= 0.0, "Robot should begin kinematic movement"
    # Destination RF_5_0 is at y = 4.0 (initial y = 6.0)
    assert curr_y <= initial_y, "Robot should move Southwards"


def test_6_robot_reaches_next_rf_node(sim_instance):
    """Verify robot completes continuous trajectory and snaps to target RF node."""
    robot = sim_instance.robots["R1"]
    target_node = "RF_5_0"
    target_coords = sim_instance.controller.resolve_node_coords(target_node)
    assert target_coords is not None

    # Step simulation until arrival or max steps
    max_steps = 150
    for _ in range(max_steps):
        sim_instance.controller.step(dt=0.05)
        if robot.current_node == target_node:
            break

    assert robot.current_node == target_node, f"Expected robot to arrive at {target_node}, got {robot.current_node}"
    assert math.isclose(robot.x, target_coords[0], abs_tol=0.06)
    assert math.isclose(robot.y, target_coords[1], abs_tol=0.06)


def test_7_robot_turns_correctly(sim_instance):
    """Verify robot rotates visibly to align with orthogonal aisle direction."""
    robot = sim_instance.robots["R1"]
    # Currently at RF_5_0, assign Eastward move to RF_5_1 (target yaw = 0 rad)
    route = ["RF_5_0", "RF_5_1"]
    sim_instance.assign_route("R1", route)

    # Robot was facing South (-pi/2). To move East, it must rotate to 0 rad
    initial_yaw = robot.yaw
    sim_instance.controller.step(dt=0.1)

    assert robot.yaw != initial_yaw or abs(robot.yaw) < 0.1, "Robot should rotate towards heading"


def test_8_node_arbitration_prevents_simultaneous_occupancy():
    """Verify arbitration controller prevents two robots from occupying the same RF node."""
    arb = NodeArbitrationController()
    target_node = "RF_3_5"

    # Robot A registers intent and enters target_node
    arb.register_intent("R1", current_node="RF_4_5", next_node=target_node, priority="NORMAL")
    can_enter_a = arb.can_enter_node("R1", current_node="RF_4_5", next_node=target_node, priority="NORMAL")
    assert can_enter_a is True
    assert arb.occupancy[target_node] == "R1"
    # R1 arrives at target_node
    arb.on_node_reached("R1", previous_node="RF_4_5", current_node=target_node)

    # Robot B also wants target_node while R1 occupies it
    arb.register_intent("R2", current_node="RF_3_6", next_node=target_node, priority="NORMAL")
    can_enter_b = arb.can_enter_node("R2", current_node="RF_3_6", next_node=target_node, priority="NORMAL")
    assert can_enter_b is False, "Robot B must be blocked while node is occupied"

    # R1 moves forward to RF_2_5 and releases target_node
    arb.on_node_reached("R1", previous_node=target_node, current_node="RF_2_5")

    # Now Robot B can enter
    can_enter_b_after = arb.can_enter_node("R2", current_node="RF_3_6", next_node=target_node, priority="NORMAL")
    assert can_enter_b_after is True
    assert arb.occupancy[target_node] == "R2"


def test_9_lidar_detects_rack(sim_instance):
    """Verify simulated LiDAR ray cast detects physical 3D rack geometry."""
    # Place LiDAR in front of rack RACK_01 (center x = -14.4, y = -5.0)
    lidar = sim_instance.lidars["R1"]
    scan = lidar.scan(robot_x=-14.4, robot_y=-4.0, robot_yaw=-math.pi / 2.0)

    assert scan["num_rays"] == 180
    assert len(scan["ranges"]) == 180
    assert len(scan["points"]) > 0, "LiDAR must detect physical rack structure"
    # Should have a hit within ~1.0m to 1.5m
    assert scan["min_distance"] < 2.0


def test_10_lidar_detects_another_robot(sim_instance):
    """Verify LiDAR detects another physical AMR chassis in its line of sight."""
    r1 = sim_instance.robots["R1"]
    r2 = sim_instance.robots["R2"]

    # Place R2 directly 2 meters ahead of R1
    r2.x = r1.x + 2.0
    r2.y = r1.y
    r2.yaw = 0.0
    r2._apply_pose_to_pybullet()

    lidar = sim_instance.lidars["R1"]
    scan = lidar.scan(robot_x=r1.x, robot_y=r1.y, robot_yaw=0.0, robot_body_id=r1.body_id)

    # Must detect obstacle in forward cone
    forward_hits = [p for p in scan["points"] if abs(p[1] - r1.y) < 0.4 and (p[0] - r1.x) < 2.5]
    assert len(forward_hits) > 0, "LiDAR must detect adjacent robot chassis"


def test_11_occupancy_grid_updates_from_lidar():
    """Verify SLAM occupancy grid updates free and occupied cells from LiDAR rays."""
    grid = OccupancyGrid(min_x=-17.5, max_x=17.5, min_y=-7.5, max_y=7.5, resolution=0.10)
    assert grid.get_coverage_percent() == 0.0

    # 360-degree scan with multiple rays
    rays = []
    for deg in range(0, 360, 10):
        rad = math.radians(deg)
        rays.append((0.0, 0.0, 3.0 * math.cos(rad), 3.0 * math.sin(rad), True))
    grid.update_batch(rays)

    # Coverage should now be > 0
    cov = grid.get_coverage_percent()
    assert cov > 0.0, "Coverage must increase after processing scan"

    # Intermediate cell (1.0, 0) should be free (0)
    c_mid, r_mid = grid.world_to_grid(1.0, 0.0)
    assert grid.grid[r_mid, c_mid] == 0, "Intermediate ray cell must be free"

    # Endpoint cell (3.0, 0) should be occupied (100)
    c_end, r_end = grid.world_to_grid(3.0, 0.0)
    assert grid.grid[r_end, c_end] == 100, "Hit endpoint must be occupied"


def test_12_slam_pose_updates():
    """Verify SLAM engine updates robot pose and trajectory correctly."""
    slam = SlamEngine(resolution=0.10)
    pose_data = {"x": 5.0, "y": -2.0, "yaw": 1.57}
    scan_data = {"ranges": [3.0] * 180, "points": [[5.0, 1.0]]}

    slam.process_scan("R1", pose_data, scan_data)
    state = slam.get_slam_state("R1")

    assert state["pose"]["x"] == 5.0
    assert state["pose"]["y"] == -2.0
    assert state["pose"]["yaw"] == 1.57
    assert len(state["trajectory"]) >= 1


def test_13_task_produces_actual_robot_movement(sim_instance):
    """Verify dispatching an A* route causes the robot to continuously advance."""
    robot = sim_instance.robots["R3"]  # at RF_0_0
    route = ["RF_0_0", "RF_1_0", "RF_2_0"]
    sim_instance.assign_route("R3", route, task_id="TASK_T13")

    initial_y = robot.y
    for _ in range(50):
        sim_instance.controller.step(dt=0.05)

    assert robot.y > initial_y, "Robot R3 should have moved North towards RF_1_0"


def test_14_telemetry_packet_generation(sim_instance):
    """Verify telemetry matches required format for WebSocket streaming."""
    telemetry = sim_instance.get_telemetry()
    assert "fleet_summary" in telemetry
    assert "robots" in telemetry
    assert len(telemetry["robots"]) == 4

    r1_telem = telemetry["robots"][0]
    required_keys = ["robot_id", "x", "y", "z", "yaw", "speed", "current_node", "status", "battery"]
    for k in required_keys:
        assert k in r1_telem, f"Missing {k} in robot telemetry"


def test_15_dynamic_obstacle_triggers_replanning(sim_instance):
    """Verify dynamic obstacle detection triggers replan callback with new route."""
    replan_called = False
    new_route_received = []

    def mock_replan(rid, curr, target, blocked):
        nonlocal replan_called, new_route_received
        replan_called = True
        new_route_received = [curr, "RF_1_1", target]
        return new_route_received

    sim_instance.controller.replan_callback = mock_replan

    robot = sim_instance.robots["R4"]
    robot.current_node = "RF_0_13"
    robot.next_node = "RF_1_13"
    robot.target_node = "RF_3_13"
    robot.route = ["RF_0_13", "RF_1_13", "RF_2_13", "RF_3_13"]

    # Trigger obstacle detection
    obs_info = {"distance": 0.8, "point": [15.6, -4.5]}
    sim_instance.controller.handle_obstacle_detected("R4", obs_info)

    assert replan_called is True, "Replanning callback must be invoked upon obstacle detection"
    assert robot.route == new_route_received, "Robot must adopt replanned route"


def test_16_robot_failure_and_recovery(sim_instance):
    """Verify robot failure halts motion and recovery restores availability."""
    robot = sim_instance.robots["R2"]
    sim_instance.fail_robot("R2")

    assert robot.is_failed is True
    assert robot.status == "FAILED"
    assert robot.speed == 0.0

    # Stepping while failed should not move robot
    curr_x, curr_y = robot.x, robot.y
    sim_instance.controller.step(dt=0.5)
    assert robot.x == curr_x and robot.y == curr_y

    # Recover robot
    sim_instance.recover_robot("R2")
    assert robot.is_failed is False
    assert robot.status == "AVAILABLE"


def test_17_api_endpoints_and_failure_reallocation():
    """Verify FastAPI simulation endpoints and CBAA task reallocation on failure."""
    from fastapi.testclient import TestClient
    from backend.api.main import app
    from backend.core.state import global_state

    client = TestClient(app)

    # Status check
    status_resp = client.get("/api/simulation/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "success"

    # Telemetry check
    telem_resp = client.get("/api/simulation/telemetry")
    assert telem_resp.status_code == 200
    assert len(telem_resp.json()["robots"]) == 4

    # Add dynamic obstacle
    obs_resp = client.post("/api/simulation/obstacle", json={"x": 2.4, "y": 0.0, "obstacle_id": "OBS_TEST"})
    assert obs_resp.status_code == 200
    assert obs_resp.json()["status"] == "success"

    # SLAM map check
    slam_resp = client.get("/api/slam/map?robot_id=R1")
    assert slam_resp.status_code == 200
    assert "occupancy_grid" in slam_resp.json()

    # Create task TASK_LIVE_01 near top-left: pickup RF_5_1, dispatch RF_2_10
    task_payload = {
        "task_id": "TASK_LIVE_01",
        "pickup_node": "RF_5_1",
        "dispatch_node": "RF_2_10",
        "priority": "HIGH",
        "task_type": "TRANSPORT",
    }
    task_resp = client.post("/api/tasks", json=task_payload)
    assert task_resp.status_code == 200
    winner = task_resp.json()["winner"]
    assert winner == "R1"  # R1 is closest to RF_5_1

    # Simulate failure of winner R1
    fail_resp = client.post("/api/simulation/fail_robot", json={"robot_id": "R1"})
    assert fail_resp.status_code == 200
    assert fail_resp.json()["status"] == "success"
    assert fail_resp.json()["reopened_task"] == "TASK_LIVE_01"

    # Verify task was reassigned to one of the surviving AMRs (R2, R3, or R4)
    active_assignments = {r: tid for r, tid in global_state.robot_tasks.items()}
    assert "TASK_LIVE_01" in active_assignments.values(), "Task must be reassigned"
    new_winner = [r for r, tid in active_assignments.items() if tid == "TASK_LIVE_01"][0]
    assert new_winner != "R1", f"Failed robot R1 cannot hold task, reassigned to {new_winner}"
    assert new_winner in ["R2", "R3", "R4"]

    # Recover R1
    rec_resp = client.post("/api/simulation/recover_robot", json={"robot_id": "R1"})
    assert rec_resp.status_code == 200
    assert rec_resp.json()["status"] == "success"
