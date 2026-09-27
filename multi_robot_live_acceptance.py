from __future__ import annotations

import concurrent.futures
import math
import sys
import time
from typing import Dict, List, Tuple

from edge_agents.planning.local_planner import LocalPlanner
from edge_agents.robot_agent.agent import EdgeRobotAgent
from edge_agents.simulation.coppeliasim_adapter import CoppeliaSimAdapter
from edge_agents.simulation.coppeliasim_bridge import CoppeliaSimMotionBridge
from edge_agents.simulation.warehouse_scene import WarehouseConfig, build_navigation_graph, build_node_to_world


def check_manhattan_pair(node_a: str, node_b: str) -> bool:
    try:
        r_a, c_a = [int(x) for x in node_a.split("_")[1:3]]
        r_b, c_b = [int(x) for x in node_b.split("_")[1:3]]
        return abs(r_a - r_b) + abs(c_a - c_b) == 1
    except Exception:
        return False


def main() -> bool:
    print("=" * 60)
    print("SWARM-X MULTI-ROBOT CONCURRENT ACCEPTANCE DEMO")
    print("=" * 60, flush=True)

    config = WarehouseConfig()
    node_map = build_node_to_world(config)
    nav_graph = build_navigation_graph(config)

    # Four distinct, valid orthogonal paths across 4 quadrants
    paths: Dict[str, List[str]] = {
        "R1": ["RF_0_0", "RF_0_1", "RF_0_2", "RF_1_2", "RF_2_2"],
        "R2": ["RF_9_9", "RF_9_8", "RF_9_7", "RF_8_7", "RF_7_7"],
        "R3": ["RF_0_9", "RF_1_9", "RF_2_9", "RF_2_8", "RF_2_7"],
        "R4": ["RF_9_0", "RF_8_0", "RF_7_0", "RF_7_1", "RF_7_2"],
    }

    # STEP 1: Pre-Execution Validation
    print("\n--- 1. PRE-EXECUTION PATH VALIDATION ---")
    all_paths_valid = True
    for robot_id, path in paths.items():
        # Validate path with bridge static validator
        bridge_valid = CoppeliaSimMotionBridge.validate_path(path, node_map)

        # Confirm all nodes exist
        nodes_exist = all(node in node_map for node in path)

        # Confirm every consecutive pair is Manhattan-adjacent
        pairs_adjacent = all(check_manhattan_pair(a, b) for a, b in zip(path, path[1:]))

        path_ok = bridge_valid and nodes_exist and pairs_adjacent
        if not path_ok:
            all_paths_valid = False

        path_str = " -> ".join(path)
        print(f"{robot_id}: {path_str}")
        print(f"  {robot_id}_VALID={bridge_valid}")
        print(f"  {robot_id}_NODES_EXIST={nodes_exist}")
        print(f"  {robot_id}_MANHATTAN_ADJACENT={pairs_adjacent}")

    print(f"ALL_PATHS_VALID={all_paths_valid}", flush=True)
    if not all_paths_valid:
        print("ERROR: One or more paths failed pre-validation.")
        return False

    # STEP 2: Edge-Agent Coordination & Arbitration Verification
    print("\n--- 2. EDGE-AGENT COORDINATION & TRAFFIC ARBITRATION ---")
    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    intents = {}
    for rid, agent in agents.items():
        path = paths[rid]
        intent = agent.build_intent(
            task_id=f"TASK_{rid}",
            current_node=path[0],
            next_node=path[1],
            planned_path=path,
            eta=2.5,
            priority="NORMAL",
        )
        intents[rid] = intent
        print(f"{rid}_INTENT: from {intent['payload']['current_node']} towards {intent['payload']['next_node']} (len={len(path)})")

    # Verify arbitration helper
    arbitration_reqs = [
        {"robot_id": "R1", "priority": "HIGH", "eta": 3.0, "intersection": "X1"},
        {"robot_id": "R2", "priority": "NORMAL", "eta": 2.0, "intersection": "X1"},
    ]
    winner = EdgeRobotAgent.arbitrate_intersection(arbitration_reqs)
    print(f"ARBITRATION_TEST_WINNER={winner}")

    # Verify deadlock / wait cycle detector
    cycle_check = EdgeRobotAgent.detect_wait_cycle({"R1": "R2", "R2": "R1"})
    print(f"WAIT_CYCLE_DETECTION={cycle_check['cycle_detected']}")

    # STEP 3: Connect to CoppeliaSim & Reset Robots to Start Nodes
    print("\n--- 3. CONNECTING TO COPPELIASIM & INITIALIZING POSITIONS ---")
    setup_bridge = CoppeliaSimMotionBridge(robot_ids=["R1", "R2", "R3", "R4"])
    setup_bridge.set_node_map(node_map)
    setup_bridge.connect(timeout=10.0)
    print("SETUP_BRIDGE_CONNECTED=True")

    for rid, path in paths.items():
        handle = setup_bridge._resolve_robot_handle(rid)
        start_node = path[0]
        start_xy = node_map[start_node]
        setup_bridge.sim.setObjectPosition(handle, -1, [start_xy[0], start_xy[1], 0.12])
        setup_bridge.sim.setObjectOrientation(handle, -1, [0.0, 0.0, 0.0])
        curr_pos = setup_bridge.sim.getObjectPosition(handle, -1)
        print(f"{rid}_INITIAL_POSITION={curr_pos} (at {start_node})")

    setup_bridge.disconnect()
    print("SETUP_BRIDGE_DISCONNECTED=True", flush=True)

    # STEP 4: Concurrent Execution of All 4 Robots
    print("\n--- 4. CONCURRENT LIVE EXECUTION ---")
    print("Starting concurrent execution of R1, R2, R3, R4...", flush=True)

    def _execute_robot(rid: str, path: List[str]) -> Tuple[str, bool, List[float]]:
        # Dedicated client connection per edge agent
        b = CoppeliaSimMotionBridge(robot_ids=[rid], speed=1.2)
        b.set_node_map(node_map)
        b.connect(timeout=10.0)
        try:
            ok = b.execute_path(rid, path, step_delay=0.03)
            final_pos = b.sim.getObjectPosition(b._resolve_robot_handle(rid), -1)
            return rid, ok, list(final_pos)
        finally:
            b.disconnect()

    exec_start = time.time()
    exec_results: Dict[str, bool] = {}
    final_positions: Dict[str, List[float]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {
            executor.submit(_execute_robot, rid, paths[rid]): rid
            for rid in ["R1", "R2", "R3", "R4"]
        }
        for future in concurrent.futures.as_completed(future_map):
            rid = future_map[future]
            try:
                r_id, ok, f_pos = future.result()
                exec_results[r_id] = ok
                final_positions[r_id] = f_pos
                print(f"  {r_id} completed: ok={ok}, final_pos={f_pos}", flush=True)
            except Exception as exc:
                print(f"  {rid} failed with exception: {exc}", flush=True)
                exec_results[rid] = False

    exec_duration = time.time() - exec_start
    print(f"CONCURRENT_EXECUTION_TIME={exec_duration:.2f}s", flush=True)

    # STEP 5: Final Acceptance Tolerance Verification
    print("\n--- 5. FINAL ACCEPTANCE TOLERANCE VERIFICATION ---")
    tolerance = 0.75  # Established acceptance tolerance
    all_at_target = True

    for rid, path in paths.items():
        target_node = path[-1]
        target_xy = node_map[target_node]
        pos = final_positions.get(rid, [999.0, 999.0, 999.0])
        dist = math.hypot(pos[0] - target_xy[0], pos[1] - target_xy[1])
        at_node = dist <= tolerance
        if not at_node:
            all_at_target = False
        print(f"{rid}_TARGET_NODE={target_node} (expected xy: {target_xy})")
        print(f"{rid}_FINAL={pos}")
        print(f"{rid}_DISTANCE_TO_TARGET={dist:.4f}m")
        print(f"{rid}_AT_{target_node}={at_node}")

    multi_robot_ok = (
        len(exec_results) == 4
        and all(exec_results.values())
        and all_at_target
    )

    print("\n" + "=" * 60)
    print(f"MULTI_ROBOT_EXECUTION_OK={multi_robot_ok}")
    print(f"R1_FINAL={final_positions.get('R1')}")
    print(f"R2_FINAL={final_positions.get('R2')}")
    print(f"R3_FINAL={final_positions.get('R3')}")
    print(f"R4_FINAL={final_positions.get('R4')}")
    print("=" * 60, flush=True)

    return multi_robot_ok


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
