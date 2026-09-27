import pytest
import asyncio
from core.state import global_state
from models.schemas import Robot, Task
from simulation.engine import simulator
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.main import run_planning
from coordination.deadlock import dependency_graph

def setup_function():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.reset()
    dependency_graph.clear()
    simulator.current_time_step = 0
    from models.schemas import Node
    for i in range(10):
        neighbors = []
        if i > 0: neighbors.append(f"N{i-1}")
        if i < 9: neighbors.append(f"N{i+1}")
        
        global_state.add_node(Node(
            node_id=f"N{i}",
            x=float(i),
            y=0.0,
            type="WAYPOINT",
            neighbors=neighbors,
            health=100.0
        ))

@pytest.mark.asyncio
async def test_conflict_no_deadlock():
    # TEST 1 - NORMAL CONFLICT
    global_state.robots["R1"] = Robot(robot_id="R1", node_id="N0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.robots["R2"] = Robot(robot_id="R2", node_id="N2", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    
    # R1 goes N0 -> N2
    # R2 goes N2 -> N0
    
    # We will manually reserve R2's path N2 -> N1 -> N0 at t=0,1,2
    reservation_manager.reserve_path("R2", [
        {"node_id": "N2", "time_step": 0},
        {"node_id": "N1", "time_step": 1},
        {"node_id": "N0", "time_step": 2}
    ])
    
    # Let's run planning for R1 to N2
    global_state.tasks["T1"] = Task(task_id="T1", pickup_node="N0", dispatch_node="N2", priority="HIGH", urgency=1.0, deadline=100.0, load=1.0, energy_requirement=10.0)
    global_state.robot_tasks["R1"] = "T1"
    
    # R1 planning should find an alternate path (wait at N0 until N1 is free at t=2)
    # Expected wait:
    # t=0: N0
    # t=1: N0
    # t=2: N0 (since R2 arrives at N0 at t=2, actually R1 can't be at N0 at t=2!)
    # Wait, R1 is AT N0. If R2 comes to N0 at t=2, they will vertex conflict at N0 at t=2!
    pass

    # Actually let's make it simpler.
    # N0 - N1 - N2 - N3
    # R1 at N0. R2 at N2.
    # R2 wants to go N2 -> N3. (t=0 N2, t=1 N3)
    # R1 wants to go N0 -> N2 -> N3. (t=0 N0, t=1 N1, t=2 N2, t=3 N3)
    # No conflict.
    
    # Let's force a temporal wait conflict.
    # R2 reserves N2 at t=2.
    reservation_manager.reset()
    reservation_manager.reserve_path("R2", [
        {"node_id": "N2", "time_step": 2}
    ])
    
    res = await run_planning("R1", "T1", start_time=0)
    assert res.get("error") is None
    assert metrics_tracker.deadlocks_detected == 0
    # Proves ordinary conflict doesn't trigger deadlock
    
@pytest.mark.asyncio
async def test_two_robot_deadlock():
    # TEST 2 - TWO ROBOT DEADLOCK
    global_state.robots["R1"] = Robot(robot_id="R1", node_id="N1", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.robots["R2"] = Robot(robot_id="R2", node_id="N2", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    
    global_state.tasks["T1"] = Task(task_id="T1", pickup_node="N1", dispatch_node="N2", priority="HIGH", urgency=1.0, deadline=100.0, load=1.0, energy_requirement=10.0)
    global_state.tasks["T2"] = Task(task_id="T2", pickup_node="N2", dispatch_node="N1", priority="HIGH", urgency=1.0, deadline=100.0, load=1.0, energy_requirement=10.0)
    
    global_state.robot_tasks["R1"] = "T1"
    global_state.robot_tasks["R2"] = "T2"
    
    # Setup mutual reservations to simulate cyclic blocking
    # R1 reserves N1 forever
    # R2 reserves N2 forever
    # In time-space A*, they try to cross but can't because both nodes are blocked
    # Actually, if we just make them block each other:
    # A* will explore and fail if bounds exceeded. But standard bounds are large.
    # We can explicitly simulate the failure.
    
    # Let's explicitly block R2 by having R1 reserve N1 for a long time
    reservation_manager.reserve_path("R1", [
        {"node_id": "N1", "time_step": t} for t in range(500)
    ])
    
    dependency_graph.add_dependency("R1", "R2")
    dependency_graph.add_dependency("R2", "R1")
    
    assert dependency_graph.has_cycle() == True
    
    # Now run recovery
    from coordination.deadlock import recover_deadlock
    cycles = dependency_graph.detect_cycles()
    
    # determinism check: R2 should yield because R1 and R2 have equal priority, equal urgency, equal battery, but R2 > R1 string ID.
    assert dependency_graph.select_yielding_robot(cycles[0]) == "R2"
    
    success = await recover_deadlock(cycles[0])
    
    assert metrics_tracker.deadlock_recovery_attempts == 3
    assert metrics_tracker.deadlock_recovery_failures == 1

@pytest.mark.asyncio
async def test_three_robot_cycle():
    # TEST 3 - THREE ROBOT CYCLE
    dependency_graph.add_dependency("R1", "R2")
    dependency_graph.add_dependency("R2", "R3")
    dependency_graph.add_dependency("R3", "R1")
    
    cycles = dependency_graph.detect_cycles()
    assert len(cycles) == 1
    
    global_state.robots["R1"] = Robot(robot_id="R1", node_id="N1", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.robots["R2"] = Robot(robot_id="R2", node_id="N2", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.robots["R3"] = Robot(robot_id="R3", node_id="N3", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    
    # Determinism: R3 yields
    assert dependency_graph.select_yielding_robot(cycles[0]) == "R3"
