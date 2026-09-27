from __future__ import annotations

import concurrent.futures
import math
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from edge_agents.common.state import NeighborState
from edge_agents.robot_agent.agent import EdgeRobotAgent
from edge_agents.simulation.coppeliasim_bridge import CoppeliaSimMotionBridge
from edge_agents.simulation.controller import NodeArbitrationController
from edge_agents.simulation.warehouse_scene import WarehouseConfig, build_node_to_world


def check_manhattan_pair(node_a: str, node_b: str) -> bool:
    try:
        r_a, c_a = [int(x) for x in node_a.split("_")[1:3]]
        r_b, c_b = [int(x) for x in node_b.split("_")[1:3]]
        return abs(r_a - r_b) + abs(c_a - c_b) == 1
    except Exception:
        return False


def run_contested_intersection_demo() -> bool:
    print("=" * 65)
    print("SWARM-X CONTESTED INTERSECTION ACCEPTANCE DEMO (LIVE)")
    print("=" * 65, flush=True)

    config = WarehouseConfig()
    node_map = build_node_to_world(config)
    contested_node = "RF_5_5"
    target_xy = node_map[contested_node]
    node_tolerance = 0.75  # 0.75m radius around node center

    # Define routes converging orthogonally on RF_5_5
    # R1: RF_5_3 -> RF_5_4 -> RF_5_5 -> RF_5_6
    # R2: RF_3_5 -> RF_4_5 -> RF_5_5
    path_r1 = ["RF_5_3", "RF_5_4", "RF_5_5", "RF_5_6"]
    path_r2 = ["RF_3_5", "RF_4_5", "RF_5_5"]

    # -------------------------------------------------------------
    # 1. Path Validation
    # -------------------------------------------------------------
    print("\n--- 1. PRE-EXECUTION PATH VALIDATION ---")
    r1_valid = CoppeliaSimMotionBridge.validate_path(path_r1, node_map)
    r2_valid = CoppeliaSimMotionBridge.validate_path(path_r2, node_map)
    r1_nodes_ok = all(n in node_map for n in path_r1)
    r2_nodes_ok = all(n in node_map for n in path_r2)
    r1_manhattan = all(check_manhattan_pair(a, b) for a, b in zip(path_r1, path_r1[1:]))
    r2_manhattan = all(check_manhattan_pair(a, b) for a, b in zip(path_r2, path_r2[1:]))

    conflict_paths_valid = (
        r1_valid and r2_valid and r1_nodes_ok and r2_nodes_ok and r1_manhattan and r2_manhattan
    )
    print(f"R1 Path: {' -> '.join(path_r1)} (Valid={r1_valid}, NodesExist={r1_nodes_ok}, Manhattan={r1_manhattan})")
    print(f"R2 Path: {' -> '.join(path_r2)} (Valid={r2_valid}, NodesExist={r2_nodes_ok}, Manhattan={r2_manhattan})")
    print(f"CONFLICT_PATHS_VALID={conflict_paths_valid}", flush=True)

    if not conflict_paths_valid:
        print("ERROR: Paths failed validation.")
        return False

    # -------------------------------------------------------------
    # 2. Setup Agents and Arbitration
    # -------------------------------------------------------------
    print("\n--- 2. EDGE AGENT ARBITRATION INITIALIZATION ---")
    agent_r1 = EdgeRobotAgent("R1")
    agent_r2 = EdgeRobotAgent("R2")
    agent_r1.state.current_node = "RF_5_3"
    agent_r2.state.current_node = "RF_3_5"

    req_r1 = {
        "robot_id": "R1",
        "priority": "HIGH",
        "eta": 1.5,
        "intersection": contested_node,
    }
    req_r2 = {
        "robot_id": "R2",
        "priority": "NORMAL",
        "eta": 1.5,
        "intersection": contested_node,
    }

    winner = EdgeRobotAgent.arbitrate_intersection([req_r1, req_r2])
    loser = "R2" if winner == "R1" else "R1"
    print(f"ARBITRATION_WINNER={winner}")
    print(f"ARBITRATION_LOSER={loser}")

    controller = NodeArbitrationController({"R1": agent_r1, "R2": agent_r2})
    controller.set_priority("R1", "HIGH")
    controller.set_priority("R2", "NORMAL")
    controller.register_agent(agent_r1, initial_node="RF_5_3")
    controller.register_agent(agent_r2, initial_node="RF_3_5")

    # Pre-register intent for upcoming paths
    controller.register_intent("R1", "RF_5_3", contested_node, eta=1.5, priority="HIGH", planned_path=path_r1)
    controller.register_intent("R2", "RF_3_5", contested_node, eta=1.5, priority="NORMAL", planned_path=path_r2)

    # -------------------------------------------------------------
    # 3. Connection to CoppeliaSim & Reset Positions
    # -------------------------------------------------------------
    print("\n--- 3. CONNECTING TO COPPELIASIM & INITIALIZING POSITIONS ---")
    setup_bridge = CoppeliaSimMotionBridge(robot_ids=["R1", "R2"])
    setup_bridge.set_node_map(node_map)
    print("CONNECT_ATTEMPT", flush=True)
    try:
        setup_bridge.connect(timeout=10.0)
        print("CONNECTED=True", flush=True)
    except Exception as exc:
        print(f"CONNECTION_FAILED: {exc}", flush=True)
        return False

    try:
        h1 = setup_bridge._resolve_robot_handle("R1")
        h2 = setup_bridge._resolve_robot_handle("R2")
        pos_r1_start = node_map["RF_5_3"]
        pos_r2_start = node_map["RF_3_5"]
        setup_bridge.sim.setObjectPosition(h1, -1, [pos_r1_start[0], pos_r1_start[1], 0.12])
        setup_bridge.sim.setObjectOrientation(h1, -1, [0.0, 0.0, 0.0])
        setup_bridge.sim.setObjectPosition(h2, -1, [pos_r2_start[0], pos_r2_start[1], 0.12])
        setup_bridge.sim.setObjectOrientation(h2, -1, [0.0, 0.0, 0.0])
        init_p1 = setup_bridge.sim.getObjectPosition(h1, -1)
        init_p2 = setup_bridge.sim.getObjectPosition(h2, -1)
        print(f"R1 placed at RF_5_3: {init_p1}")
        print(f"R2 placed at RF_3_5: {init_p2}")
    finally:
        setup_bridge.disconnect()

    # -------------------------------------------------------------
    # 4. Continuous Physical Monitoring Setup
    # -------------------------------------------------------------
    print("\n--- 4. LAUNCHING CONTINUOUS COORDINATE MONITORING ---")
    pos_lock = threading.Lock()
    latest_positions: Dict[str, List[float]] = {
        "R1": [pos_r1_start[0], pos_r1_start[1], 0.12],
        "R2": [pos_r2_start[0], pos_r2_start[1], 0.12],
    }
    coordinate_samples: List[Dict[str, Any]] = []
    simultaneous_occupancy_violations: List[Dict[str, Any]] = []

    winner_entered_event: Optional[float] = None
    winner_exited_event: Optional[float] = None
    loser_entered_event: Optional[float] = None

    def record_step_position(rid: str, pos: Sequence[float]) -> None:
        nonlocal winner_entered_event, winner_exited_event, loser_entered_event
        t = time.time()
        with pos_lock:
            latest_positions[rid] = [float(pos[0]), float(pos[1]), float(pos[2])]
            p1 = latest_positions["R1"]
            p2 = latest_positions["R2"]

            d1 = math.hypot(p1[0] - target_xy[0], p1[1] - target_xy[1])
            d2 = math.hypot(p2[0] - target_xy[0], p2[1] - target_xy[1])

            in_node_r1 = (d1 <= node_tolerance)
            in_node_r2 = (d2 <= node_tolerance)

            sample = {
                "t": t,
                "r1": p1[:2],
                "r2": p2[:2],
                "d_r1": d1,
                "d_r2": d2,
                "r1_in": in_node_r1,
                "r2_in": in_node_r2,
            }
            coordinate_samples.append(sample)

            # Track entry / exit times based on empirical physical positions
            d_winner = d1 if winner == "R1" else d2
            d_loser = d2 if winner == "R1" else d1

            if d_winner <= node_tolerance:
                if winner_entered_event is None:
                    winner_entered_event = t
                    print(f"[{t:.3f}] PHYSICAL_MONITOR: {winner} ENTERED {contested_node} (dist={d_winner:.3f}m)", flush=True)
            elif winner_entered_event is not None and winner_exited_event is None:
                # Winner has moved away from contested node
                winner_exited_event = t
                print(f"[{t:.3f}] PHYSICAL_MONITOR: {winner} EXITED {contested_node} (dist={d_winner:.3f}m)", flush=True)

            if d_loser <= node_tolerance:
                if loser_entered_event is None:
                    loser_entered_event = t
                    print(f"[{t:.3f}] PHYSICAL_MONITOR: {loser} ENTERED {contested_node} (dist={d_loser:.3f}m)", flush=True)

            if in_node_r1 and in_node_r2:
                simultaneous_occupancy_violations.append(sample)
                print(f"[{t:.3f}] VIOLATION DETECTED: BOTH in node! d_r1={d1:.3f}m, d_r2={d2:.3f}m", flush=True)

    # Background polling thread for continuous CoppeliaSim coordinate verification
    stop_monitor = threading.Event()

    def monitor_loop():
        m_bridge = CoppeliaSimMotionBridge(robot_ids=["R1", "R2"])
        try:
            m_bridge.connect(timeout=5.0)
            mh1 = m_bridge._resolve_robot_handle("R1")
            mh2 = m_bridge._resolve_robot_handle("R2")
            while not stop_monitor.is_set():
                p1 = m_bridge.sim.getObjectPosition(mh1, -1)
                p2 = m_bridge.sim.getObjectPosition(mh2, -1)
                record_step_position("R1", p1)
                record_step_position("R2", p2)
                time.sleep(0.04)
        except Exception as exc:
            # Monitoring loop error is non-fatal if robot threads are updating positions
            pass
        finally:
            m_bridge.disconnect()

    monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()

    # -------------------------------------------------------------
    # 5. Concurrent Execution with Node Arbitration
    # -------------------------------------------------------------
    print("\n--- 5. CONCURRENT LIVE EXECUTION ---")
    print(f"R1 Path: {' -> '.join(path_r1)}")
    print(f"R2 Path: {' -> '.join(path_r2)}")

    def _execute_robot(rid: str, path: List[str]) -> Tuple[str, bool, List[float]]:
        b = CoppeliaSimMotionBridge(robot_ids=[rid], speed=1.2)
        b.set_node_map(node_map)
        b.connect(timeout=10.0)
        try:
            ok = b.execute_path(
                rid,
                path,
                step_delay=0.03,
                can_enter_node=controller.can_enter_node,
                on_node_reached=controller.on_node_reached,
                on_step=record_step_position,
                wait_poll_delay=0.05,
                max_wait_timeout=25.0,
            )
            handle = b._resolve_robot_handle(rid)
            final_pos = list(b.sim.getObjectPosition(handle, -1))
            return rid, ok, final_pos
        finally:
            b.disconnect()

    exec_start = time.time()
    results: Dict[str, Tuple[bool, List[float]]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(_execute_robot, "R1", path_r1)
        f2 = executor.submit(_execute_robot, "R2", path_r2)
        r1_id, r1_ok, r1_final = f1.result()
        r2_id, r2_ok, r2_final = f2.result()
        results[r1_id] = (r1_ok, r1_final)
        results[r2_id] = (r2_ok, r2_final)

    stop_monitor.set()
    monitor_thread.join(timeout=2.0)
    exec_duration = time.time() - exec_start
    print(f"Execution finished in {exec_duration:.2f}s", flush=True)

    # -------------------------------------------------------------
    # 6. Physical Evidence Analysis
    # -------------------------------------------------------------
    print("\n--- 6. PHYSICAL EVIDENCE ANALYSIS ---")
    
    # 1. Did the loser physically wait?
    wait_events = [e for e in controller.event_log if e["event"] == "WAIT" and e.get("robot_id") == loser]
    loser_waited = len(wait_events) >= 1
    print(f"LOSER_WAITED={loser_waited} (Total WAIT events for {loser}: {len(wait_events)})")

    # 2. Winner entry and exit verification from measured coordinates
    winner_entered = winner_entered_event is not None
    # Winner exited: winner entered, then moved to final destination away from contested node
    target_winner_dest = node_map[path_r1[-1] if winner == "R1" else path_r2[-1]]
    winner_final_pos = r1_final if winner == "R1" else r2_final
    dist_winner_to_dest = math.hypot(winner_final_pos[0] - target_winner_dest[0], winner_final_pos[1] - target_winner_dest[1])
    dist_winner_to_contested = math.hypot(winner_final_pos[0] - target_xy[0], winner_final_pos[1] - target_xy[1])
    winner_exited = winner_entered and (dist_winner_to_contested > node_tolerance) and (dist_winner_to_dest <= node_tolerance)

    print(f"WINNER_ENTERED={winner_entered} (at t={winner_entered_event})")
    print(f"WINNER_EXITED={winner_exited} (final dist to node={dist_winner_to_contested:.3f}m, dist to dest={dist_winner_to_dest:.3f}m)")

    # 3. Loser entry verification
    target_loser_dest = node_map[path_r2[-1] if winner == "R1" else path_r1[-1]]
    loser_final_pos = r2_final if winner == "R1" else r1_final
    dist_loser_to_dest = math.hypot(loser_final_pos[0] - target_loser_dest[0], loser_final_pos[1] - target_loser_dest[1])
    loser_entered = (loser_entered_event is not None) and (dist_loser_to_dest <= node_tolerance)
    print(f"LOSER_ENTERED={loser_entered} (at t={loser_entered_event}, final dist to dest={dist_loser_to_dest:.3f}m)")

    # 4. No simultaneous occupancy from measured positions
    no_simultaneous_occupancy = (len(simultaneous_occupancy_violations) == 0)
    print(f"NO_SIMULTANEOUS_OCCUPANCY={no_simultaneous_occupancy} (Violations: {len(simultaneous_occupancy_violations)}, Total samples: {len(coordinate_samples)})")

    # 5. Final destinations
    r1_dest_xy = node_map["RF_5_6"]
    r2_dest_xy = node_map["RF_5_5"]
    r1_dest_dist = math.hypot(r1_final[0] - r1_dest_xy[0], r1_final[1] - r1_dest_xy[1])
    r2_dest_dist = math.hypot(r2_final[0] - r2_dest_xy[0], r2_final[1] - r2_dest_xy[1])
    r1_dest_ok = r1_dest_dist <= node_tolerance
    r2_dest_ok = r2_dest_dist <= node_tolerance

    print(f"R1 Final: {r1_final} (dist to RF_5_6={r1_dest_dist:.4f}m, OK={r1_dest_ok})")
    print(f"R2 Final: {r2_final} (dist to RF_5_5={r2_dest_dist:.4f}m, OK={r2_dest_ok})")

    # Overall Demo Success
    conflict_demo_success = (
        conflict_paths_valid
        and loser_waited
        and winner_entered
        and winner_exited
        and loser_entered
        and no_simultaneous_occupancy
        and r1_dest_ok
        and r2_dest_ok
    )

    print("\n" + "=" * 65)
    print(f"CONFLICT_PATHS_VALID={conflict_paths_valid}")
    print(f"ARBITRATION_WINNER={winner}")
    print(f"LOSER_WAITED={loser_waited}")
    print(f"WINNER_ENTERED={winner_entered}")
    print(f"WINNER_EXITED={winner_exited}")
    print(f"LOSER_ENTERED={loser_entered}")
    print(f"NO_SIMULTANEOUS_OCCUPANCY={no_simultaneous_occupancy}")
    print(f"R1_FINAL={r1_final}")
    print(f"R2_FINAL={r2_final}")
    print(f"CONFLICT_DEMO_SUCCESS={conflict_demo_success}")
    print("=" * 65, flush=True)

    return conflict_demo_success


if __name__ == "__main__":
    success = run_contested_intersection_demo()
    sys.exit(0 if success else 1)
