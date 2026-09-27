from __future__ import annotations

from edge_agents.robot_agent.agent import EdgeRobotAgent


def test_four_agents_can_compute_local_bid_independently():
    task = {
        "task_id": "T_EDGE_01",
        "pickup_node": "N_0_1",
        "dispatch_node": "N_0_2",
        "priority": "HIGH",
        "urgency": 1.5,
        "deadline": 120.0,
        "load": 1.0,
        "energy_requirement": 10.0,
    }

    agents = {rid: EdgeRobotAgent(rid) for rid in ["R1", "R2", "R3", "R4"]}
    for agent in agents.values():
        agent.state.battery = 95.0

    results = {
        rid: agent.local_decision_test(task)
        for rid, agent in agents.items()
    }

    assert len(results) == 4
    assert all("bid" in v for v in results.values())
    assert all(v["feasible"] is True for v in results.values())
    assert min(v["bid"] for v in results.values()) >= 0.0


def test_agent_can_determine_winner_without_central_logic():
    agent = EdgeRobotAgent("R1")
    bids = {
        "R1": {"feasible": True, "bid": 12.0},
        "R2": {"feasible": True, "bid": 18.0},
        "R3": {"feasible": True, "bid": 15.5},
        "R4": {"feasible": False, "bid": float("inf")},
    }

    winner = agent.determine_winner(bids)
    assert winner == "R1"


def test_message_envelope_has_required_fields():
    from edge_agents.communication.protocol import MessageEnvelope

    msg = MessageEnvelope("HEARTBEAT", "R2", 7, 123.0, {"battery": 88.0})
    data = msg.to_dict()

    assert data["msg_type"] == "HEARTBEAT"
    assert data["sender_id"] == "R2"
    assert data["seq"] == 7
    assert data["payload"]["battery"] == 88.0
