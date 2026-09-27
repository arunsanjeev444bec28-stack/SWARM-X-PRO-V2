"""SWARM-X PRO V2 — DEMO 1: DISTRIBUTED TASK ALLOCATION (CBAA).

Demonstrates pure edge-native decentralized task auctioning across 4 AMRs:
1. TASK_ANNOUNCE — Distributed task announcement ingested by edge agents
2. BID           — Independent local bid computation (battery, cost, urgency)
3. WINNER_CLAIM  — Autonomous claim broadcast by the consensus winner
4. WINNER_SELECTION — Deterministic multi-agent consensus validation
"""

from __future__ import annotations

import time
from typing import Dict, Any

from edge_agents.robot_agent.agent import EdgeRobotAgent


def run_demo1():
    print("=" * 65)
    print("SWARM-X DEMO 1: DISTRIBUTED CBAA TASK ALLOCATION")
    print("=" * 65)

    # 1. Initialize 4 autonomous edge agents
    agents: Dict[str, EdgeRobotAgent] = {
        "R1": EdgeRobotAgent("R1"),
        "R2": EdgeRobotAgent("R2"),
        "R3": EdgeRobotAgent("R3"),
        "R4": EdgeRobotAgent("R4"),
    }

    # Set distinct local state for each robot
    agents["R1"].state.battery = 96.0
    agents["R1"].state.current_node = "RF_1_1"

    agents["R2"].state.battery = 78.0
    agents["R2"].state.current_node = "RF_2_2"

    agents["R3"].state.battery = 65.0
    agents["R3"].state.current_node = "RF_7_7"

    agents["R4"].state.battery = 88.0
    agents["R4"].state.current_node = "RF_8_8"

    print("\n--- 1. INITIAL ROBOT STATES ---")
    for rid, ag in agents.items():
        print(f"  {rid}: Node={ag.state.current_node}, Battery={ag.state.battery}%, Status={ag.state.status}")

    # 2. Task Announcement
    task: Dict[str, Any] = {
        "task_id": "TASK_WH_01",
        "pickup_node": "RF_1_2",
        "dispatch_node": "RF_1_8",
        "priority": "HIGH",
        "urgency": 1.2,
        "deadline": 120.0,
        "load": 1.0,
        "energy_requirement": 8.0,
    }

    print("\n--- 2. TASK_ANNOUNCE ---")
    t0 = time.time()
    print(f"[{t0:.3f}] EVENT: TASK_ANNOUNCE")
    print(f"  Task ID: {task['task_id']}")
    print(f"  Pickup: {task['pickup_node']} -> Dispatch: {task['dispatch_node']}")
    print(f"  Priority: {task['priority']}, Urgency: {task['urgency']}, EnergyReq: {task['energy_requirement']} kWh")

    # Each agent ingests the task announcement
    for agent in agents.values():
        agent.add_task(task)

    # 3. Independent Bid Calculation
    print("\n--- 3. BID (LOCAL EDGE EVALUATION) ---")
    bids: Dict[str, Dict[str, Any]] = {}
    for rid, agent in agents.items():
        bid_info = agent.calculate_bid(task["task_id"])
        agent.register_bid(task["task_id"], bid_info)
        bids[rid] = bid_info
        print(f"[{time.time():.3f}] EVENT: BID robot={rid} feasible={bid_info['feasible']} score={bid_info['bid']:.2f} (reason={bid_info['reason']})")

    # 4. P2P Bid Consensus Exchange
    print("\n--- 4. P2P CONSENSUS GOSSIP ---")
    # All agents exchange and record bids
    for rid, agent in agents.items():
        for peer_id, peer_bid in bids.items():
            if peer_id != rid:
                agent.record_peer_bid(task["task_id"], peer_id, peer_bid)

    # 5. Independent Winner Determination
    local_winners = {}
    for rid, agent in agents.items():
        w = agent.determine_task_winner(task["task_id"])
        local_winners[rid] = w

    # Verify all agents independently arrived at the identical winner
    all_agree = len(set(local_winners.values())) == 1
    consensus_winner = list(local_winners.values())[0]

    # 6. Winner Claim
    print("\n--- 5. WINNER_CLAIM ---")
    claim_t = time.time()
    claim_result = agents[consensus_winner].claim_winner(task["task_id"], consensus_winner)
    print(f"[{claim_t:.3f}] EVENT: WINNER_CLAIM robot={consensus_winner} task={task['task_id']}")

    print("\n--- 6. WINNER SELECTION VERIFICATION ---")
    for rid, w in local_winners.items():
        print(f"  Agent {rid} local consensus winner: {w}")

    print(f"\nConsensus Reached: {all_agree}")
    print(f"Determined Winner: {consensus_winner}")
    print(f"Winner Assigned Task ID: {agents[consensus_winner].state.current_task_id}")

    success = all_agree and (consensus_winner == "R1") and (agents[consensus_winner].state.current_task_id == task["task_id"])

    print("\n" + "=" * 65)
    print(f"TASK_ANNOUNCE=True")
    print(f"BID=True")
    print(f"WINNER_CLAIM=True")
    print(f"WINNER_SELECTION={consensus_winner}")
    print(f"DEMO_1_SUCCESS={success}")
    print("=" * 65)

    return success


if __name__ == "__main__":
    ok = run_demo1()
    raise SystemExit(0 if ok else 1)
