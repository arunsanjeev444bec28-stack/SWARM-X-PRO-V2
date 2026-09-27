import asyncio
import sys
import os

# Ensure backend path is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.schemas import Node, Robot, Task
from core.state import global_state
from api.main import run_allocation, run_planning, start_simulation
from evaluation.metrics import metrics_tracker
from simulation.engine import simulator

async def run_test():
    # 1. Setup 4x4 Grid
    # Node IDs: N_{x}_{y}
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

    # 2. Add Robots
    # Robot 1 at N_0_1
    r1 = Robot(
        robot_id="R1", node_id="N_0_1", battery=100.0,
        temperature=25.0, load=0.0, health=100.0, status="IDLE"
    )
    # Robot 2 at N_1_0
    r2 = Robot(
        robot_id="R2", node_id="N_1_0", battery=100.0,
        temperature=25.0, load=0.0, health=100.0, status="IDLE"
    )
    global_state.add_robot(r1)
    global_state.add_robot(r2)

    # 3. Add conflicting tasks
    # T1: Pickup at N_2_1, Dispatch at N_3_3
    # r1 path: N_0_1 -> N_1_1 -> N_2_1
    t1 = Task(
        task_id="T1", pickup_node="N_2_1", dispatch_node="N_3_3",
        priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0
    )
    # T2: Pickup at N_1_2, Dispatch at N_3_3
    # r2 path: N_1_0 -> N_1_1 -> N_1_2
    # They will both want to be at N_1_1 at time_step=1. Vertex conflict!
    t2 = Task(
        task_id="T2", pickup_node="N_1_2", dispatch_node="N_3_3",
        priority="HIGH", urgency=1.0, deadline=60.0, load=1.0, energy_requirement=5.0
    )
    global_state.add_task(t1)
    global_state.add_task(t2)

    # Force allocations for testing (R1 -> T1, R2 -> T2)
    global_state.robot_tasks["R1"] = "T1"
    r1.status = "ASSIGNED"
    
    global_state.robot_tasks["R2"] = "T2"
    r2.status = "ASSIGNED"

    # 4. Plan Paths
    print("Planning for R1...")
    res1 = await run_planning("R1", "T1", start_time=0)
    print("R1 Path:", res1['path'])
    
    print("Planning for R2...")
    res2 = await run_planning("R2", "T2", start_time=0)
    print("R2 Path:", res2['path'])
    print("R2 Replanned:", res2['replanned'])

    # 5. Run Simulation
    print("Starting simulation...")
    await start_simulation()
    
    # Wait for simulation to finish
    while simulator.is_running:
        await asyncio.sleep(0.1)
        
    print("Simulation finished.")
    
    # 6. Assert Metrics
    metrics = metrics_tracker.get_metrics()
    print("Metrics:", metrics)
    
    assert metrics['collision_count'] == 0, "Collision count should be 0"
    assert metrics['replan_count'] >= 1, "Replan count should be >= 1"
    assert metrics['alternate_path_count'] >= 1 or metrics['wait_fallback'] >= 1, "Should have alternate path or wait fallback"
    print("TEST PASSED")

if __name__ == "__main__":
    asyncio.run(run_test())
