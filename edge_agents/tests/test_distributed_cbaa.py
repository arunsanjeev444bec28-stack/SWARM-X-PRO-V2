from __future__ import annotations

import time

from edge_agents.robot_agent.agent import EdgeRobotAgent


def _make_task(task_id: str, priority: str = "HIGH"):
    return {
        "task_id": task_id,
        "pickup_node": "N_0_1",
        "dispatch_node": "N_0_2",
        "priority": priority,
        "urgency": 1.0,
        "deadline": 120.0,
        "load": 1.0,
        "energy_requirement": 10.0,
    }


def test_single_task_all_agents_agree_on_same_winner():
    task = _make_task("T_SINGLE")
    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    for agent in agents.values():
        agent.state.battery = 95.0
        agent.announce_task(task)

    bids = {rid: agent.task_bids["T_SINGLE"][rid] for rid, agent in agents.items()}
    winners = {rid: agent.determine_winner(bids) for rid, agent in agents.items()}
    assert len(set(winners.values())) == 1
    assert winners["R1"] == winners["R2"] == winners["R3"] == winners["R4"]


def test_multiple_simultaneous_tasks_are_allocated_distributedly():
    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    tasks = {f"T_{idx}": _make_task(f"T_{idx}") for idx in range(1, 4)}

    battery_map = {
        "T_1": {"R1": 97.0, "R2": 92.0, "R3": 87.0, "R4": 82.0},
        "T_2": {"R1": 82.0, "R2": 97.0, "R3": 92.0, "R4": 87.0},
        "T_3": {"R1": 87.0, "R2": 82.0, "R3": 97.0, "R4": 92.0},
    }

    assigned = {}
    for task_id, task in tasks.items():
        for rid, agent in agents.items():
            agent.state.battery = battery_map[task_id][rid]
            agent.announce_task(task)
        task_bids = {rid: agent.task_bids[task_id][rid] for rid, agent in agents.items()}
        winner = min(agents, key=lambda rid: (task_bids[rid]["bid"], rid))
        assigned[task_id] = winner

    assert len(set(assigned.values())) >= 2
    assert assigned["T_1"] == "R1"
    assert assigned["T_2"] == "R2"
    assert assigned["T_3"] == "R3"


def test_equal_bid_tie_break_is_deterministic():
    task = _make_task("T_TIE")
    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    for agent in agents.values():
        agent.state.battery = 90.0
        agent.announce_task(task)

    bids = {rid: agent.task_bids["T_TIE"][rid] for rid, agent in agents.items()}
    for bid in bids.values():
        bid["bid"] = 20.0

    winners = {rid: agent.determine_winner(bids) for rid, agent in agents.items()}
    assert len(set(winners.values())) == 1
    assert winners["R1"] == "R1"


def test_robot_failure_reopens_task_and_rebids():
    task = _make_task("T_FAIL")
    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    for rid, agent in agents.items():
        agent.state.battery = {"R1": 95.0, "R2": 92.0, "R3": 88.0, "R4": 84.0}[rid]
        agent.announce_task(task)

    bids = {rid: agent.task_bids["T_FAIL"][rid] for rid, agent in agents.items()}
    winner = min(agents, key=lambda rid: (bids[rid]["bid"], rid))
    for agent in agents.values():
        agent.claim_winner("T_FAIL", winner)

    dead_robot = winner
    for agent in agents.values():
        agent.handle_dead_robot(dead_robot, "T_FAIL")

    assert agents[dead_robot].task_ownership["T_FAIL"] is None
    assert "T_FAIL" in agents[dead_robot].task_reopened

    remaining = {rid: agent for rid, agent in agents.items() if rid != dead_robot}
    for agent in remaining.values():
        agent.announce_task(task)

    surviving_bids = {rid: agent.task_bids["T_FAIL"][rid] for rid, agent in remaining.items()}
    new_winner = min(remaining, key=lambda rid: (surviving_bids[rid]["bid"], rid))
    for agent in remaining.values():
        agent.claim_winner("T_FAIL", new_winner)

    surviving = {rid: agent.task_ownership.get("T_FAIL") for rid, agent in remaining.items()}
    assert len(set(surviving.values())) == 1
    assert list(set(surviving.values())) == [new_winner]
    assert new_winner != dead_robot
