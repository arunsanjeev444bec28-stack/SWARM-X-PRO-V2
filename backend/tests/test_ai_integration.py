import pytest
from core.state import global_state
from models.schemas import Node, Robot, Task
from allocation.cbaa import allocator

@pytest.fixture(autouse=True)
def setup_teardown():
    global_state.reset()
    yield
    global_state.reset()

def test_cbaa_ai_integration():
    # Setup simple environment
    global_state.add_node(Node(node_id="N1", x=0, y=0, type="WAYPOINT", neighbors=["N2"]))
    global_state.add_node(Node(node_id="N2", x=1, y=0, type="WAYPOINT", neighbors=["N1"]))
    
    global_state.add_robot(Robot(robot_id="R1", node_id="N1", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE"))
    global_state.add_task(Task(task_id="T1", pickup_node="N1", dispatch_node="N2", priority="HIGH", urgency=1.0, deadline=100.0, load=1.0, energy_requirement=10.0))
    
    # Enable risk weight
    allocator.risk_weight = 10.0
    
    # Calculate bid
    robot = global_state.get_robot("R1")
    task = global_state.get_task("T1")
    
    bid_info = allocator.calculate_bid_with_risk(robot, task)
    
    assert "robot_id" in bid_info
    assert "base_bid" in bid_info
    assert "risk_probability" in bid_info
    assert "risk_penalty" in bid_info
    assert "final_bid" in bid_info
    
    assert bid_info["risk_penalty"] == allocator.risk_weight * bid_info["risk_probability"]
    assert bid_info["final_bid"] == bid_info["base_bid"] + bid_info["risk_penalty"]
    
    # Allocate
    res = allocator.allocate_task("T1")
    assert res.winner == "R1"
    
    # Check that bids in response has the dictionary format
    assert "R1" in res.bids
    assert isinstance(res.bids["R1"], dict)
    assert res.bids["R1"]["final_bid"] == bid_info["final_bid"]
