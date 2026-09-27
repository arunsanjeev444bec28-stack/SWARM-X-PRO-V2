import pytest
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schemas import Node, Robot, Task
from core.state import global_state
from api.main import run_allocation, run_planning, start_simulation
from evaluation.metrics import metrics_tracker
from simulation.engine import simulator
from coordination.reservation import reservation_manager
from allocation.cbaa import allocator

@pytest.fixture(autouse=True)
def setup_teardown():
    global_state.reset()
    reservation_manager.reset()
    # Reset metrics
    metrics_tracker.completed_tasks = 0
    metrics_tracker.failed_tasks = 0
    metrics_tracker.allocation_success = 0
    metrics_tracker.total_distance = 0.0
    metrics_tracker.replan_count = 0
    metrics_tracker.collision_count = 0
    metrics_tracker.alternate_path_count = 0
    metrics_tracker.wait_fallback = 0
    metrics_tracker.reservation_conflicts = 0
    metrics_tracker.task_completion_times = []
    metrics_tracker.pickup_events = 0
    metrics_tracker.dispatch_events = 0
    simulator.is_running = False
    simulator.current_time_step = 0

def create_4x4_grid():
    for x in range(4):
        for y in range(4):
            neighbors = []
            if x > 0: neighbors.append(f"N_{x-1}_{y}")
            if x < 3: neighbors.append(f"N_{x+1}_{y}")
            if y > 0: neighbors.append(f"N_{x}_{y-1}")
            if y < 3: neighbors.append(f"N_{x}_{y+1}")
            
            node = Node(
                node_id=f"N_{x}_{y}",
                x=float(x),
                y=float(y),
                type="NORMAL",
                neighbors=neighbors
            )
            global_state.add_node(node)

@pytest.mark.asyncio
async def test_wait_fallback_integration():
    create_4x4_grid()

    # R1 crosses N_1_1 at t=1
    r1 = Robot(robot_id="R1", node_id="N_0_1", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    # R2 wants to cross N_1_1 at t=1. Waiting is cheaper than detour because it's a 4x4 grid and only 1 step wait is needed.
    r2 = Robot(robot_id="R2", node_id="N_1_0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r1)
    global_state.add_robot(r2)

    t1 = Task(task_id="T1", pickup_node="N_2_1", dispatch_node="N_3_3", priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0)
    t2 = Task(task_id="T2", pickup_node="N_1_2", dispatch_node="N_3_3", priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0)
    global_state.add_task(t1)
    global_state.add_task(t2)

    # 1. Test CBAA Allocation
    res1_alloc = await run_allocation("T1")
    assert res1_alloc["winner"] == "R1" # Heuristically closer
    assert len(res1_alloc["feasible_robots"]) == 2
    assert "R1" in res1_alloc["bids"]
    assert "R2" in res1_alloc["bids"]
    
    res2_alloc = await run_allocation("T2")
    assert res2_alloc["winner"] == "R2"
    
    assert metrics_tracker.allocation_success == 2

    # 2. Plan Paths
    res1 = await run_planning("R1", "T1", start_time=0)
    res2 = await run_planning("R2", "T2", start_time=0)
    
    # 3. Run Simulation
    await start_simulation()
    
    await asyncio.sleep(0.2)
    
    timeout = 100
    while simulator.is_running and timeout > 0:
        await asyncio.sleep(0.1)
        timeout -= 1
        
    metrics = metrics_tracker.get_metrics()
    
    assert metrics['collision_count'] == 0
    assert metrics['completed_tasks'] == 2
    assert metrics['pickup_events'] == 2
    assert metrics['dispatch_events'] == 2
    
    assert metrics['wait_fallback'] == 1
    assert metrics['alternate_path_count'] == 0


@pytest.mark.asyncio
async def test_spatial_alternate_path_integration():
    create_4x4_grid()

    # We want R2 to find a spatial alternate path.
    # If R1 parks at N_1_1 for 5 timesteps (by moving back and forth or just reserving it heavily).
    # Since we can't easily force R1 to wait without modifying the task to take longer, 
    # we can manually reserve N_1_1 for t=1 through t=5.
    reservation_manager.vertex_reservations[("N_1_1", 1)] = "R1"
    reservation_manager.vertex_reservations[("N_1_1", 2)] = "R1"
    reservation_manager.vertex_reservations[("N_1_1", 3)] = "R1"
    reservation_manager.vertex_reservations[("N_1_1", 4)] = "R1"
    reservation_manager.vertex_reservations[("N_1_1", 5)] = "R1"

    # R2 starts at N_1_0 and needs to get to N_3_3. 
    # Normal shortest path would be N_1_0 -> N_1_1 -> ... taking 5 steps.
    # But N_1_1 is blocked from t=1 to t=5.
    # Waiting at N_1_0 would mean waiting 5 timesteps (total time 5 + 5 = 10).
    # Detouring through N_0_0 -> N_0_1 -> N_0_2 -> N_1_2 takes maybe 7 steps (total time 7).
    # A* should prefer the spatial detour (time 7) over waiting (time 10).
    
    r2 = Robot(robot_id="R2", node_id="N_1_0", battery=100.0, temperature=25.0, load=0.0, health=100.0, status="IDLE")
    global_state.add_robot(r2)
    
    t2 = Task(task_id="T2", pickup_node="N_1_2", dispatch_node="N_3_3", priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0)
    global_state.add_task(t2)
    
    # 1. Allocation
    res2_alloc = await run_allocation("T2")
    assert res2_alloc["winner"] == "R2"
    
    # 2. Planning
    res2 = await run_planning("R2", "T2", start_time=0)
    
    # 3. Validation without simulation (we just want to check planning metrics)
    assert res2["replanned"] is True
    
    # Wait fallback might still be incremented if it tried something else, but alternate_path_count MUST be >= 1
    # Actually wait, our logic compares `unconstrained_path` to `path`.
    # Detour means they will differ spatially.
    metrics = metrics_tracker.get_metrics()
    
    assert metrics['alternate_path_count'] == 1
    assert metrics['wait_fallback'] == 0
    
    # 4. Simulation
    await start_simulation()
    await asyncio.sleep(0.2)
    
    timeout = 100
    while simulator.is_running and timeout > 0:
        await asyncio.sleep(0.1)
        timeout -= 1
        
    metrics = metrics_tracker.get_metrics()
    assert metrics['collision_count'] == 0
    assert metrics['completed_tasks'] == 1
