import pytest
import asyncio
from core.state import global_state
from simulation.engine import simulator
from models.schemas import Robot, Task, Node, FailureRequest
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.main import inject_failure, run_planning, run_allocation
from api.websocket import manager

class MockWS:
    async def broadcast(self, data):
        pass

manager.broadcast = MockWS().broadcast

@pytest.mark.asyncio
async def test_robot_failure_reauction():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.robot_failures = 0
    metrics_tracker.tasks_reauctioned = 0
    metrics_tracker.successful_reassignments = 0
    
    # 0 - 1 - 2
    for i in range(3):
        global_state.add_node(Node(node_id=f"N{i}", x=float(i), y=0, type="NORMAL", neighbors=[]))
    global_state.get_node("N0").neighbors = ["N1"]
    global_state.get_node("N1").neighbors = ["N0", "N2"]
    global_state.get_node("N2").neighbors = ["N1"]
    
    r1 = Robot(robot_id="R1", node_id="N0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    r2 = Robot(robot_id="R2", node_id="N2", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    global_state.add_robot(r2)
    
    t1 = Task(task_id="T1", pickup_node="N0", dispatch_node="N1", priority="HIGH", urgency=1.0, deadline=60.0, load=0.0, energy_requirement=1.0)
    global_state.add_task(t1)
    
    global_state.robot_tasks["R1"] = "T1"
    res = await run_planning("R1", "T1", start_time=0)
    assert res["path"] == ["N0", "N1"]
    
    # R1 fails
    req = FailureRequest(robot_id="R1")
    await inject_failure(req)
    
    # Check states
    assert global_state.get_robot("R1").status == "FAILED"
    assert "R1" not in global_state.robot_tasks
    assert metrics_tracker.robot_failures == 1
    assert metrics_tracker.tasks_reauctioned == 1
    
    # Yield to let the async tasks (if any) or synchronous ones take effect
    await asyncio.sleep(0.1)
    
    # T1 should be reallocated to R2
    assert global_state.robot_tasks.get("R2") == "T1"
    assert metrics_tracker.successful_reassignments == 1
    
    # And R2 should have a path
    assert "R2" in global_state.robot_paths
