import pytest
import asyncio
from core.state import global_state
from simulation.engine import simulator
from models.schemas import Robot, Task, Node, Obstacle
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.main import create_obstacle, run_planning
from api.websocket import manager

class MockWS:
    async def broadcast(self, data):
        pass

manager.broadcast = MockWS().broadcast

@pytest.mark.asyncio
async def test_dynamic_obstacle_replanning():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.obstacle_replans = 0
    metrics_tracker.dynamic_obstacle_events = 0
    simulator.current_time_step = 0
    
    # 0 - 1 - 2
    # |       |
    # 3 - 4 - 5
    for i in range(6):
        global_state.add_node(Node(node_id=f"N{i}", x=float(i%3), y=float(i//3), type="NORMAL", neighbors=[]))
    global_state.get_node("N0").neighbors = ["N1", "N3"]
    global_state.get_node("N1").neighbors = ["N0", "N2"]
    global_state.get_node("N2").neighbors = ["N1", "N5"]
    global_state.get_node("N3").neighbors = ["N0", "N4"]
    global_state.get_node("N4").neighbors = ["N3", "N5"]
    global_state.get_node("N5").neighbors = ["N2", "N4"]
    
    r1 = Robot(robot_id="R1", node_id="N0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    t1 = Task(task_id="T1", pickup_node="N0", dispatch_node="N2", priority="HIGH", urgency=1.0, deadline=60.0, load=0.0, energy_requirement=1.0)
    global_state.add_task(t1)
    
    global_state.robot_tasks["R1"] = "T1"
    
    res = await run_planning("R1", "T1", start_time=0)
    assert res["path"] == ["N0", "N1", "N2"]
    
    # R1 is scheduled to be at N1 at t=1
    
    # Create an obstacle on N1 for duration 5
    obs = Obstacle(node_id="N1", duration=5)
    await create_obstacle(obs)
    
    assert global_state.dynamic_obstacles["N1"] == 5
    assert metrics_tracker.dynamic_obstacle_events == 1
    
    # Yield to let the async replan run
    await asyncio.sleep(0.1)
    
    assert metrics_tracker.obstacle_replans >= 1
    
    # Check that new path avoids N1
    path_info = global_state.robot_paths["R1"]
    new_path_nodes = [step.node_id for step in path_info["trajectory"]]
    # Should route N0 -> N3 -> N4 -> N5 -> N2
    assert "N1" not in new_path_nodes
    assert "N3" in new_path_nodes
