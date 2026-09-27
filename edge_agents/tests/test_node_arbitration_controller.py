from __future__ import annotations

import concurrent.futures
import time
from edge_agents.common.state import NeighborState
from edge_agents.robot_agent.agent import EdgeRobotAgent
from edge_agents.simulation.controller import NodeArbitrationController


def test_controller_registers_initial_occupancy():
    r1 = EdgeRobotAgent("R1")
    r2 = EdgeRobotAgent("R2")
    controller = NodeArbitrationController()

    controller.register_agent(r1, initial_node="RF_5_3")
    controller.register_agent(r2, initial_node="RF_3_5")

    assert controller.occupancy.get("RF_5_3") == "R1"
    assert controller.occupancy.get("RF_3_5") == "R2"


def test_controller_occupancy_exclusion_prevents_simultaneous_entry():
    r1 = EdgeRobotAgent("R1")
    r2 = EdgeRobotAgent("R2")
    controller = NodeArbitrationController()
    controller.register_agent(r1, initial_node="RF_5_4")
    controller.register_agent(r2, initial_node="RF_5_5")

    # R1 attempts to enter RF_5_5 while R2 occupies it
    allowed = controller.can_enter_node("R1", "RF_5_4", "RF_5_5")
    assert allowed is False
    assert controller.occupancy["RF_5_5"] == "R2"

    wait_events = [e for e in controller.event_log if e["event"] == "WAIT"]
    assert len(wait_events) >= 1
    assert wait_events[-1]["robot_id"] == "R1"
    assert "occupied by r2" in wait_events[-1]["reason"].lower()


def test_controller_arbitration_and_sequential_release():
    r1 = EdgeRobotAgent("R1")
    r2 = EdgeRobotAgent("R2")
    controller = NodeArbitrationController({"R1": r1, "R2": r2})
    controller.occupancy["RF_5_4"] = "R1"
    controller.occupancy["RF_4_5"] = "R2"

    # Both robots announce intent for RF_5_5; R1 has HIGH priority, R2 has NORMAL priority
    controller.register_intent("R2", "RF_4_5", "RF_5_5", eta=2.0, priority="NORMAL")
    controller.register_intent("R1", "RF_5_4", "RF_5_5", eta=1.5, priority="HIGH")

    # R2 requests entry: should be denied because R1 is competing and has higher priority
    r2_denied = controller.can_enter_node("R2", "RF_4_5", "RF_5_5", eta=2.0, priority="NORMAL")
    assert r2_denied is False

    # R1 requests entry: should be granted because R1 wins arbitration
    r1_allowed = controller.can_enter_node("R1", "RF_5_4", "RF_5_5", eta=1.5, priority="HIGH")
    assert r1_allowed is True
    assert controller.occupancy["RF_5_5"] == "R1"

    # R2 attempts entry while R1 is winner / holding RF_5_5
    r2_allowed = controller.can_enter_node("R2", "RF_4_5", "RF_5_5", eta=2.0, priority="NORMAL")
    assert r2_allowed is False

    # Check arbitration events
    arb_events = [e for e in controller.event_log if e["event"] == "ARBITRATION"]
    assert len(arb_events) >= 1
    assert arb_events[-1]["winner"] == "R1"

    # R1 completes move through RF_5_5 into RF_5_6
    controller.on_node_reached("R1", "RF_5_4", "RF_5_5")
    controller.on_node_reached("R1", "RF_5_5", "RF_5_6")

    # RF_5_5 should now be vacant
    assert "RF_5_5" not in controller.occupancy

    exit_events = [e for e in controller.event_log if e["event"] == "EXIT_NODE" and e["node_id"] == "RF_5_5"]
    assert len(exit_events) == 1
    assert exit_events[0]["robot_id"] == "R1"

    # Now R2 re-evaluates: should be granted permission
    r2_allowed_after = controller.can_enter_node("R2", "RF_4_5", "RF_5_5", eta=1.0, priority="NORMAL")
    assert r2_allowed_after is True
    assert controller.occupancy["RF_5_5"] == "R2"


def test_controller_concurrent_threads_mutual_exclusion():
    r1 = EdgeRobotAgent("R1")
    r2 = EdgeRobotAgent("R2")
    controller = NodeArbitrationController({"R1": r1, "R2": r2})
    controller.set_priority("R1", "HIGH")
    controller.set_priority("R2", "NORMAL")
    controller.register_agent(r1, initial_node="RF_5_4")
    controller.register_agent(r2, initial_node="RF_4_5")

    # Register initial intents for the contested node
    controller.register_intent("R1", "RF_5_4", "RF_5_5", eta=1.0)
    controller.register_intent("R2", "RF_4_5", "RF_5_5", eta=1.0)

    occupancy_history = []
    r2_waited = False

    def run_r1():
        # R1 requests entry, holds for 0.05s, then exits
        assert controller.can_enter_node("R1", "RF_5_4", "RF_5_5") is True
        occupancy_history.append(controller.occupancy.get("RF_5_5"))
        time.sleep(0.05)
        controller.on_node_reached("R1", "RF_5_4", "RF_5_5")
        # R1 exits RF_5_5 to RF_5_6
        assert controller.can_enter_node("R1", "RF_5_5", "RF_5_6") is True
        controller.on_node_reached("R1", "RF_5_5", "RF_5_6")

    def run_r2():
        nonlocal r2_waited
        # R2 tries to enter RF_5_5; should wait until R1 clears
        start = time.time()
        while not controller.can_enter_node("R2", "RF_4_5", "RF_5_5"):
            r2_waited = True
            time.sleep(0.01)
            if time.time() - start > 2.0:
                raise TimeoutError("R2 timed out")
        occupancy_history.append(controller.occupancy.get("RF_5_5"))
        controller.on_node_reached("R2", "RF_4_5", "RF_5_5")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        f1 = ex.submit(run_r1)
        f2 = ex.submit(run_r2)
        f1.result()
        f2.result()

    assert r2_waited is True
    # At no time were both in RF_5_5
    assert controller.occupancy.get("RF_5_5") == "R2"
    assert "RF_5_4" not in controller.occupancy


def test_may_enter_node_direct_agent_interface():
    agent = EdgeRobotAgent("R1")

    # Clear when no neighbors or peer conflicts
    assert agent.may_enter_node("RF_5_5") is True

    # Denied when neighbor occupies the target node
    agent.neighbors["R2"] = NeighborState(
        robot_id="R2",
        last_seen=100.0,
        status="MOVING",
        current_node="RF_5_5",
        target_node="RF_5_5",
    )
    assert agent.may_enter_node("RF_5_5") is False

    # Remove neighbor occupancy
    agent.neighbors.clear()

    # Conflicting peer requests: R1 with NORMAL vs R2 with CRITICAL
    peers = [
        {"robot_id": "R2", "priority": "CRITICAL", "eta": 1.0, "intersection": "RF_5_5"}
    ]
    assert agent.may_enter_node("RF_5_5", peer_requests=peers, priority="NORMAL") is False

    # Conflicting peer requests: R1 with CRITICAL vs R2 with LOW
    peers_low = [
        {"robot_id": "R2", "priority": "LOW", "eta": 2.0, "intersection": "RF_5_5"}
    ]
    assert agent.may_enter_node("RF_5_5", peer_requests=peers_low, priority="CRITICAL") is True
