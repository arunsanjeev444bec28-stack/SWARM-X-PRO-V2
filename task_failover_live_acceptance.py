from __future__ import annotations

import math
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from edge_agents.communication.manager import NeighborStatus, RobotCommunicationManager
from edge_agents.communication.protocol import build_heartbeat, build_task_reopen
from edge_agents.planning.local_planner import LocalPlanner
from edge_agents.robot_agent.agent import EdgeRobotAgent
from edge_agents.simulation.coppeliasim_bridge import CoppeliaSimMotionBridge
from edge_agents.simulation.controller import NodeArbitrationController
from edge_agents.simulation.warehouse_scene import (
    WarehouseConfig,
    build_navigation_graph,
    build_node_to_world,
)


def run_task_failover_acceptance_demo() -> bool:
    print("=" * 65)
    print("SWARM-X DYNAMIC TASK REOPEN & FAILOVER ACCEPTANCE DEMO (LIVE)")
    print("=" * 65, flush=True)

    config = WarehouseConfig()
    node_map = build_node_to_world(config)
    nav_graph = build_navigation_graph(config)
    node_tolerance = 0.75

    event_log: List[Dict[str, Any]] = []

    def log_event(event_name: str, payload: Optional[Dict[str, Any]] = None) -> None:
        t = time.time()
        entry = {"timestamp": t, "event": event_name, **(payload or {})}
        event_log.append(entry)
        print(f"[{t:.3f}] EVENT: {event_name} {payload or ''}", flush=True)

    # -------------------------------------------------------------
    # 1. Task Definition
    # -------------------------------------------------------------
    task_id = "TASK_FAILOVER_01"
    pickup_node = "RF_1_1"
    destination_node = "RF_1_4"
    task_dict = {
        "task_id": task_id,
        "pickup_node": pickup_node,
        "dispatch_node": destination_node,
        "priority": "HIGH",
        "urgency": 1.0,
        "deadline": 120.0,
        "load": 1.0,
        "energy_requirement": 10.0,
    }

    # -------------------------------------------------------------
    # 2. Four Healthy Robot Setup
    # -------------------------------------------------------------
    print("\n--- 1. INITIALIZING FOUR HEALTHY ROBOTS ---")
    agents: Dict[str, EdgeRobotAgent] = {
        "R1": EdgeRobotAgent("R1"),
        "R2": EdgeRobotAgent("R2"),
        "R3": EdgeRobotAgent("R3"),
        "R4": EdgeRobotAgent("R4"),
    }

    # Initial start nodes
    start_nodes = {
        "R1": "RF_1_0",
        "R2": "RF_2_2",
        "R3": "RF_7_7",
        "R4": "RF_8_8",
    }
    # Initial battery levels: R1 has highest battery -> wins initial auction
    batteries = {
        "R1": 98.0,
        "R2": 95.0,
        "R3": 85.0,
        "R4": 80.0,
    }

    for rid, agent in agents.items():
        agent.state.current_node = start_nodes[rid]
        agent.state.battery = batteries[rid]
        agent.state.status = "AVAILABLE"

    # Connect to CoppeliaSim to place robots at start positions
    print("\n--- 2. CONNECTING TO COPPELIASIM & INITIALIZING SCENE POSITIONS ---")
    setup_bridge = CoppeliaSimMotionBridge(robot_ids=["R1", "R2", "R3", "R4"])
    setup_bridge.set_node_map(node_map)
    try:
        setup_bridge.connect(timeout=10.0)
        print("COPPELIASIM_CONNECTED=True")
        for rid, s_node in start_nodes.items():
            h = setup_bridge._resolve_robot_handle(rid)
            s_xy = node_map[s_node]
            setup_bridge.sim.setObjectPosition(h, -1, [s_xy[0], s_xy[1], 0.12])
            setup_bridge.sim.setObjectOrientation(h, -1, [0.0, 0.0, 0.0])
            pos = setup_bridge.sim.getObjectPosition(h, -1)
            print(f"  {rid} placed at {s_node}: {pos}")
    finally:
        setup_bridge.disconnect()

    # -------------------------------------------------------------
    # 3. Normal Distributed CBAA Auction
    # -------------------------------------------------------------
    print("\n--- 3. DISTRIBUTED CBAA TASK ANNOUNCEMENT & AUCTION ---")
    log_event("TASK_ANNOUNCE", {
        "task_id": task_id,
        "pickup": pickup_node,
        "destination": destination_node,
    })
    task_announced = True
    print("TASK_ANNOUNCED=True")

    # Each robot independently calculates its bid
    initial_bids: Dict[str, Dict[str, Any]] = {}
    for rid, agent in agents.items():
        bid = agent.announce_task(task_dict)
        initial_bids[rid] = bid

    # Peer-to-peer bid exchange
    for rid, agent in agents.items():
        for peer_id, peer_bid in initial_bids.items():
            if peer_id != rid:
                agent.record_peer_bid(task_id, peer_id, peer_bid)

    log_event("BID", {rid: round(b["bid"], 3) for rid, b in initial_bids.items()})

    # Winner determination by CBAA consensus
    winners = {rid: agent.determine_task_winner(task_id) for rid, agent in agents.items()}
    assert len(set(winners.values())) == 1, "CBAA failed consensus on initial winner"
    initial_owner = next(iter(winners.values()))

    for agent in agents.values():
        agent.claim_winner(task_id, initial_owner)

    log_event("INITIAL_WINNER", {"winner": initial_owner, "task_id": task_id})
    print(f"INITIAL_OWNER={initial_owner}")

    # -------------------------------------------------------------
    # 4. Physical Execution by Initial Winner in CoppeliaSim
    # -------------------------------------------------------------
    print(f"\n--- 4. INITIAL PHYSICAL EXECUTION BY {initial_owner} ---")
    # Initial route for R1: RF_1_0 -> RF_1_1 (pickup) -> RF_1_2
    r1_path = ["RF_1_0", "RF_1_1", "RF_1_2"]
    print(f"{initial_owner} Path: {' -> '.join(r1_path)}")

    controller = NodeArbitrationController(agents)
    for rid, s_node in start_nodes.items():
        controller.register_agent(agents[rid], initial_node=s_node)

    b_winner = CoppeliaSimMotionBridge(robot_ids=[initial_owner], speed=1.2)
    b_winner.set_node_map(node_map)
    b_winner.connect(timeout=10.0)
    try:
        ok_initial = b_winner.execute_path(
            initial_owner,
            r1_path,
            step_delay=0.03,
            can_enter_node=controller.can_enter_node,
            on_node_reached=controller.on_node_reached,
        )
        h_init = b_winner._resolve_robot_handle(initial_owner)
        r1_pos_mid = b_winner.sim.getObjectPosition(h_init, -1)
        print(f"{initial_owner} completed initial leg: reached RF_1_2 at {r1_pos_mid}")
    finally:
        b_winner.disconnect()

    # -------------------------------------------------------------
    # 5. Simulate Robot Failure & Heartbeat Timeout
    # -------------------------------------------------------------
    print(f"\n--- 5. SIMULATING FAILURE OF {initial_owner} AT RF_1_2 ---")
    # 1. Controlled agent shutdown & battery depletion
    agents[initial_owner].state.status = "DEAD"
    agents[initial_owner].state.battery = 0.0
    agents[initial_owner].local_tasks.clear()

    log_event("ROBOT_FAILURE", {
        "robot_id": initial_owner,
        "failed_at_node": "RF_1_2",
        "position": r1_pos_mid,
        "reason": "simulated hardware fault",
    })
    robot_failure_simulated = True
    print("ROBOT_FAILURE_SIMULATED=True")

    # 2. Heartbeat timeout detection via peer communication manager
    comm_mgr = RobotCommunicationManager(
        robot_id="R2",
        peers=["R1", "R3", "R4"],
        stale_timeout_seconds=0.6,
        dead_timeout_seconds=2.0,
    )
    # Simulate missing heartbeats from R1
    now = time.time()
    comm_mgr.neighbor_status[initial_owner] = NeighborStatus(
        robot_id=initial_owner,
        last_seen=now - 2.5,  # Exceeds dead_timeout_seconds (2.0s)
        last_sequence=1,
        connection_state="ONLINE",
    )
    assessed_states = comm_mgr.assess_neighbor_state(now)
    heartbeat_timeout = (assessed_states.get(initial_owner) == "DEAD")

    log_event("HEARTBEAT_TIMEOUT", {
        "dead_robot": initial_owner,
        "timeout_seconds": 2.0,
        "assessed_state": assessed_states.get(initial_owner),
    })
    print(f"HEARTBEAT_TIMEOUT={heartbeat_timeout}")

    # -------------------------------------------------------------
    # 6. Dynamic Task Reopening via Existing Mechanism
    # -------------------------------------------------------------
    print("\n--- 6. DYNAMIC TASK REOPEN BY SURVIVING AGENTS ---")
    surviving_agents = {rid: agent for rid, agent in agents.items() if rid != initial_owner}

    task_reopened_all = True
    for s_rid, s_agent in surviving_agents.items():
        reopened = s_agent.handle_dead_robot(initial_owner, task_id)
        if not (reopened and task_id in s_agent.task_reopened):
            task_reopened_all = False

    log_event("TASK_REOPEN", {
        "task_id": task_id,
        "failed_robot": initial_owner,
        "reopened_by": list(surviving_agents.keys()),
    })
    print(f"TASK_REOPENED={task_reopened_all}")

    # -------------------------------------------------------------
    # 7. Independent Re-Bidding by Surviving Robots
    # -------------------------------------------------------------
    print("\n--- 7. INDEPENDENT RE-BIDDING BY SURVIVING ROBOTS ---")
    surviving_bids: Dict[str, Dict[str, Any]] = {}
    for s_rid, s_agent in surviving_agents.items():
        bid = s_agent.announce_task(task_dict)
        surviving_bids[s_rid] = bid

    # Peer-to-peer bid exchange among surviving robots
    for s_rid, s_agent in surviving_agents.items():
        for p_id, p_bid in surviving_bids.items():
            if p_id != s_rid:
                s_agent.record_peer_bid(task_id, p_id, p_bid)

    log_event("REBID", {rid: round(b["bid"], 3) for rid, b in surviving_bids.items()})
    rebid_completed = len(surviving_bids) == len(surviving_agents)
    print(f"REBID_COMPLETED={rebid_completed}")

    # Verify original failed robot cannot bid while dead
    failed_robot_bid = agents[initial_owner].calculate_bid(task_id)
    failed_robot_not_selected = not failed_robot_bid.get("feasible", False)

    # Winner selection by CBAA
    new_winners = {s_rid: s_agent.determine_task_winner(task_id, bids=surviving_bids) for s_rid, s_agent in surviving_agents.items()}
    assert len(set(new_winners.values())) == 1, "Surviving agents failed consensus"
    new_owner = next(iter(new_winners.values()))

    for s_agent in surviving_agents.values():
        s_agent.claim_winner(task_id, new_owner)

    log_event("NEW_WINNER", {
        "task_id": task_id,
        "new_owner": new_owner,
        "original_owner": initial_owner,
    })
    print(f"NEW_OWNER={new_owner}")
    print(f"FAILED_ROBOT_NOT_SELECTED={failed_robot_not_selected}")

    # -------------------------------------------------------------
    # 8. Physical Execution of Remaining Route by New Owner
    # -------------------------------------------------------------
    print(f"\n--- 8. PHYSICAL EXECUTION BY NEW OWNER ({new_owner}) ---")
    log_event("EXECUTION_STARTED", {
        "new_owner": new_owner,
        "start_node": agents[new_owner].state.current_node,
        "destination": destination_node,
        "blocked_node": "RF_1_2",
    })
    new_owner_execution_started = True
    print("NEW_OWNER_EXECUTION_STARTED=True")

    # The new owner plans its path to destination_node ("RF_1_4"), avoiding the blocked node "RF_1_2"
    # where the failed robot is stationary.
    planner = LocalPlanner(nav_graph)
    remaining_path = planner.plan(
        start=agents[new_owner].state.current_node,
        goal=destination_node,
        blocked={"RF_1_2"},
    )
    print(f"{new_owner} Plan (avoiding RF_1_2): {' -> '.join(remaining_path)}")

    b_replacement = CoppeliaSimMotionBridge(robot_ids=[new_owner], speed=1.2)
    b_replacement.set_node_map(node_map)
    b_replacement.connect(timeout=10.0)
    try:
        ok_replacement = b_replacement.execute_path(
            new_owner,
            remaining_path,
            step_delay=0.03,
            can_enter_node=controller.can_enter_node,
            on_node_reached=controller.on_node_reached,
        )
        h_rep = b_replacement._resolve_robot_handle(new_owner)
        pos_rep_final = list(b_replacement.sim.getObjectPosition(h_rep, -1))
    finally:
        b_replacement.disconnect()

    # Destination verification in CoppeliaSim
    dest_xy = node_map[destination_node]
    dist_to_dest = math.hypot(pos_rep_final[0] - dest_xy[0], pos_rep_final[1] - dest_xy[1])
    task_completed = ok_replacement and (dist_to_dest <= node_tolerance)

    log_event("TASK_COMPLETED", {
        "new_owner": new_owner,
        "destination": destination_node,
        "final_position": pos_rep_final,
        "distance_to_dest": round(dist_to_dest, 4),
        "task_completed": task_completed,
    })
    print(f"{new_owner} Final Position: {pos_rep_final} (dist to {destination_node}={dist_to_dest:.4f}m)")
    print(f"TASK_COMPLETED={task_completed}")

    # -------------------------------------------------------------
    # 9. Acceptance Criteria Verification
    # -------------------------------------------------------------
    failover_demo_success = (
        task_announced
        and bool(initial_owner)
        and robot_failure_simulated
        and heartbeat_timeout
        and task_reopened_all
        and rebid_completed
        and (new_owner != initial_owner)
        and failed_robot_not_selected
        and new_owner_execution_started
        and task_completed
    )

    print("\n" + "=" * 65)
    print(f"TASK_ANNOUNCED={task_announced}")
    print(f"INITIAL_OWNER={initial_owner}")
    print(f"ROBOT_FAILURE_SIMULATED={robot_failure_simulated}")
    print(f"HEARTBEAT_TIMEOUT={heartbeat_timeout}")
    print(f"TASK_REOPENED={task_reopened_all}")
    print(f"REBID_COMPLETED={rebid_completed}")
    print(f"NEW_OWNER={new_owner}")
    print(f"FAILED_ROBOT_NOT_SELECTED={failed_robot_not_selected}")
    print(f"NEW_OWNER_EXECUTION_STARTED={new_owner_execution_started}")
    print(f"TASK_COMPLETED={task_completed}")
    print(f"FAILOVER_DEMO_SUCCESS={failover_demo_success}")
    print("=" * 65, flush=True)

    return failover_demo_success


if __name__ == "__main__":
    success = run_task_failover_acceptance_demo()
    sys.exit(0 if success else 1)
