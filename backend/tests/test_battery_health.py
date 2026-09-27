import pytest
import asyncio
from core.state import global_state
from simulation.engine import simulator
from models.schemas import Robot, Task, Node
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.websocket import manager

# Mock websocket to not throw errors
class MockWS:
    async def broadcast(self, data):
        pass

manager.broadcast = MockWS().broadcast

def create_simple_grid():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.completed_tasks = 0
    metrics_tracker.battery_consumption = 0.0
    metrics_tracker.charging_events = 0
    metrics_tracker.emergency_charges = 0
    
    global_state.add_node(Node(node_id="N1", x=0, y=0, type="NORMAL", neighbors=["N2"]))
    global_state.add_node(Node(node_id="N2", x=1, y=0, type="NORMAL", neighbors=["N1", "N3"]))
    global_state.add_node(Node(node_id="N3", x=2, y=0, type="NORMAL", neighbors=["N2"]))

@pytest.mark.asyncio
async def test_battery_drain():
    create_simple_grid()
    r1 = Robot(robot_id="R1", node_id="N1", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    t1 = Task(task_id="T1", pickup_node="N1", dispatch_node="N3", priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0)
    global_state.add_task(t1)
    
    # Let's force a trajectory on it.
    from models.schemas import TrajectoryStep
    global_state.robot_paths["R1"] = {
        "trajectory": [
            TrajectoryStep(node_id="N1", time_step=0),
            TrajectoryStep(node_id="N2", time_step=1),
            TrajectoryStep(node_id="N3", time_step=2),
        ],
        "task_id": "T1",
        "pickup_time": 1
    }
    
    # Run simulation
    simulator.dt = 0.0 # Fast
    await simulator.run()
    
    # Battery should have decreased.
    assert r1.battery < 100.0
    assert metrics_tracker.battery_consumption > 0.0
    assert r1.health <= 100.0

@pytest.mark.asyncio
async def test_emergency_charging():
    create_simple_grid()
    # Battery low!
    r1 = Robot(robot_id="R1", node_id="N1", battery=21.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    t1 = Task(task_id="T1", pickup_node="N1", dispatch_node="N3", priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0)
    global_state.add_task(t1)
    
    from models.schemas import TrajectoryStep
    global_state.robot_paths["R1"] = {
        "trajectory": [
            TrajectoryStep(node_id="N1", time_step=0),
            TrajectoryStep(node_id="N2", time_step=1), # Drops below 20 here!
            TrajectoryStep(node_id="N3", time_step=2),
            TrajectoryStep(node_id="N3", time_step=3),
            TrajectoryStep(node_id="N3", time_step=4),
            TrajectoryStep(node_id="N3", time_step=5),
        ],
        "task_id": "T1",
        "pickup_time": -1
    }
    
    simulator.dt = 0.0
    global_state.robot_paths["R1"]["trajectory"] += [TrajectoryStep(node_id="N3", time_step=i) for i in range(6, 40)]
    
    await simulator.run()
    
    # Should have charged!
    assert metrics_tracker.charging_events >= 1
    assert metrics_tracker.emergency_charges >= 1
    assert r1.battery > 99.0 # Should be 100.0 and possibly drop a tiny bit if it moves after charging
    assert r1.health > 99.0

@pytest.mark.asyncio
async def test_node_health_routing():
    global_state.reset()
    reservation_manager.reset()
    # Grid 0-1-2
    #      | | |
    #      3-4-5
    for i in range(6):
        global_state.add_node(Node(node_id=f"N{i}", x=float(i%3), y=float(i//3), type="NORMAL", neighbors=[]))
    # Links
    global_state.get_node("N0").neighbors = ["N1", "N3"]
    global_state.get_node("N1").neighbors = ["N0", "N2", "N4"]
    global_state.get_node("N2").neighbors = ["N1", "N5"]
    global_state.get_node("N3").neighbors = ["N0", "N4"]
    global_state.get_node("N4").neighbors = ["N1", "N3", "N5"]
    global_state.get_node("N5").neighbors = ["N2", "N4"]

    # FAILED node
    global_state.get_node("N1").health = 10.0 # < 30 FAILED
    
    from api.main import run_planning
    r1 = Robot(robot_id="R1", node_id="N0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    t1 = Task(task_id="T1", pickup_node="N0", dispatch_node="N2", priority="HIGH", urgency=1.0, deadline=60.0, load=0.0, energy_requirement=1.0)
    global_state.add_task(t1)
    
    global_state.robot_tasks["R1"] = "T1"
    
    res = await run_planning("R1", "T1")
    # Path from N0 to N2 normally N0->N1->N2. But N1 is FAILED.
    # Must detour N0->N3->N4->N5->N2
    assert "N1" not in res["path"]
    assert res["path"] == ["N0", "N3", "N4", "N5", "N2"]
    
    # Now DEGRADED node
    global_state.get_node("N1").health = 50.0 # < 70 DEGRADED
    # Path N0->N1->N2 costs 1 + 6 = 7 (step+degraded)
    # Path N0->N3->N4->N5->N2 costs 4
    # So it still prefers the long route because penalty is 5.0
    res2 = await run_planning("R1", "T1")
    assert "N1" not in res2["path"]
    
    # If penalty was smaller or long route was longer, it might take it.
    # But since N1 is degraded, it avoids it.
    
    # If N1 is HEALTHY
    global_state.get_node("N1").health = 100.0
    res3 = await run_planning("R1", "T1")
    assert res3["path"] == ["N0", "N1", "N2"]
