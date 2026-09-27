from __future__ import annotations

from edge_agents.planning.local_planner import LocalPlanner
from edge_agents.robot_agent.agent import EdgeRobotAgent


def test_single_robot_generates_valid_astar_path():
    graph = {
        "N_0_0": {"N_0_1": 1.0},
        "N_0_1": {"N_0_0": 1.0, "N_0_2": 1.0},
        "N_0_2": {"N_0_1": 1.0},
    }
    planner = LocalPlanner(graph)
    path = planner.plan("N_0_0", "N_0_2")
    assert path == ["N_0_0", "N_0_1", "N_0_2"]


def test_two_robots_independently_generate_paths():
    r1 = EdgeRobotAgent("R1")
    r2 = EdgeRobotAgent("R2")
    r1.state.current_node = "N_0_0"
    r2.state.current_node = "N_0_3"

    p1 = r1.calculate_path({"task_id": "T_ROUTE", "pickup_node": "N_0_1", "dispatch_node": "N_0_3", "priority": "HIGH"}, start_node="N_0_0", goal_node="N_0_3")
    p2 = r2.calculate_path({"task_id": "T_ROUTE", "pickup_node": "N_0_1", "dispatch_node": "N_0_3", "priority": "HIGH"}, start_node="N_0_3", goal_node="N_0_0")

    assert p1[0] == "N_0_0"
    assert p2[0] == "N_0_3"
    assert p1[-1] == "N_0_3"
    assert p2[-1] == "N_0_0"
    assert p1 == ["N_0_0", "N_0_1", "N_0_2", "N_0_3"]
    assert p2 == ["N_0_3", "N_0_2", "N_0_1", "N_0_0"]


def test_dynamic_obstacle_invalidates_path_and_robot_replans_locally():
    agent = EdgeRobotAgent("R1")
    graph = {
        "N_0_0": {"N_0_1": 1.0, "N_0_4": 1.0},
        "N_0_1": {"N_0_0": 1.0, "N_0_2": 1.0},
        "N_0_2": {"N_0_1": 1.0, "N_0_3": 1.0},
        "N_0_3": {"N_0_2": 1.0, "N_0_4": 1.0},
        "N_0_4": {"N_0_0": 1.0, "N_0_3": 1.0},
    }
    agent.local_planner = LocalPlanner(graph)
    original = agent.calculate_path({"task_id": "T_OBS", "pickup_node": "N_0_1", "dispatch_node": "N_0_3", "priority": "HIGH"}, start_node="N_0_0", goal_node="N_0_3")
    assert original[0] == "N_0_0"
    assert original[-1] == "N_0_3"
    assert set(original).issubset({"N_0_0", "N_0_1", "N_0_2", "N_0_3", "N_0_4"})

    blocked = {"N_0_1"}
    replanned = agent.replan_path(original, blocked=blocked, start_node="N_0_0", goal_node="N_0_3")
    assert replanned[0] == "N_0_0"
    assert replanned[-1] == "N_0_3"
    assert all(node not in blocked for node in replanned)


def test_two_robots_request_same_intersection_deterministic_arbitration():
    assert EdgeRobotAgent.arbitrate_intersection([
        {"robot_id": "R2", "priority": "HIGH", "eta": 5.0, "intersection": "X_1"},
        {"robot_id": "R1", "priority": "CRITICAL", "eta": 4.0, "intersection": "X_1"},
    ]) == "R1"


def test_same_arbitration_inputs_on_all_agents_produce_same_decision():
    requests = [
        {"robot_id": "R3", "priority": "HIGH", "eta": 8.0, "intersection": "X_2"},
        {"robot_id": "R1", "priority": "HIGH", "eta": 7.0, "intersection": "X_2"},
        {"robot_id": "R2", "priority": "HIGH", "eta": 7.0, "intersection": "X_2"},
    ]
    winners = {
        rid: EdgeRobotAgent(rid).arbitrate_intersection(requests)
        for rid in ["R1", "R2", "R3", "R4"]
    }
    assert len(set(winners.values())) == 1
    assert winners["R1"] == "R1"


def test_simple_two_robot_deadlock_is_detected_and_recovered():
    wait_map = {"R1": "R2", "R2": "R1"}
    decision = EdgeRobotAgent.detect_wait_cycle(wait_map)
    assert decision["cycle_detected"] is True
    assert decision["recovery_robot"] in {"R1", "R2"}


def test_fastapi_not_required_for_local_path_planning_or_p2p_traffic_coordination():
    agent = EdgeRobotAgent("R8")
    intent = agent.build_intent(
        task_id="T_INTENT",
        current_node="N_0_1",
        next_node="N_0_2",
        planned_path=["N_0_1", "N_0_2", "N_0_3"],
        eta=12.0,
        priority="HIGH",
    )
    assert intent["msg_type"] == "INTENT"
    assert intent["payload"]["robot_id"] == "R8"
    assert intent["payload"]["task_id"] == "T_INTENT"
    assert intent["payload"]["next_node"] == "N_0_2"
