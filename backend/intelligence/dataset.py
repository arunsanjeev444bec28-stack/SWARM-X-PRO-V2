import os
import csv
import random
import asyncio
from core.state import global_state
from simulation.engine import simulator
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from coordination.deadlock import dependency_graph
from models.schemas import Node, Robot, Task
from api.main import run_planning
from intelligence.features import extract_features

async def generate_episode(seed: int, run_id: int, num_robots: int = 5, num_tasks: int = 5):
    scenario_id = f"SCENARIO_{seed}"
    random.seed(seed)
    
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.reset()
    dependency_graph.clear()
    simulator.current_time_step = 0
    
    # Occasionally degrade node health
    nodes = []
    degrade_nodes = random.random() < 0.3
    
    for x in range(5):
        for y in range(5):
            n_id = f"N_{x}_{y}"
            neighbors = []
            if x > 0: neighbors.append(f"N_{x-1}_{y}")
            if x < 4: neighbors.append(f"N_{x+1}_{y}")
            if y > 0: neighbors.append(f"N_{x}_{y-1}")
            if y < 4: neighbors.append(f"N_{x}_{y+1}")
            
            h = random.uniform(10.0, 50.0) if degrade_nodes and random.random() < 0.2 else 100.0
            global_state.add_node(Node(node_id=n_id, x=float(x), y=float(y), type="WAYPOINT", neighbors=neighbors, health=h))
            nodes.append(n_id)
            
    # Add robots
    robots = []
    for i in range(num_robots):
        r_id = f"R{i}"
        start_node = random.choice(nodes)
        
        # 20% chance of starting with very low battery
        if random.random() < 0.2:
            battery = random.uniform(5.0, 15.0)
        else:
            battery = random.uniform(20.0, 100.0)
            
        # 10% chance of high temp
        temp = random.uniform(40.0, 80.0) if random.random() < 0.1 else random.uniform(20.0, 40.0)
        
        global_state.robots[r_id] = Robot(robot_id=r_id, node_id=start_node, battery=battery, temperature=temp, load=0.0, health=100.0, status="IDLE")
        robots.append(r_id)
        
    records = []
    
    # Assign tasks randomly
    for i in range(num_tasks):
        t_id = f"T{i}"
        p_node = random.choice(nodes)
        d_node = random.choice(nodes)
        while d_node == p_node:
            d_node = random.choice(nodes)
            
        priority = random.choice(["LOW", "NORMAL", "HIGH", "CRITICAL"])
        energy = random.uniform(10.0, 80.0) # Can be very high energy
        
        # Occasionally very short deadlines
        deadline = random.uniform(10.0, 30.0) if random.random() < 0.2 else random.uniform(50.0, 200.0)
        
        global_state.tasks[t_id] = Task(task_id=t_id, pickup_node=p_node, dispatch_node=d_node, priority=priority, urgency=1.0, deadline=deadline, load=1.0, energy_requirement=energy)
        
        r_id = random.choice(robots)
        global_state.robot_tasks[r_id] = t_id
        
        # 15% chance to inject a dynamic obstacle right before extracting features
        if random.random() < 0.15:
            obs_node = random.choice(nodes)
            global_state.dynamic_obstacles[obs_node] = 1000
            
        # Extract features
        features = extract_features(r_id, t_id)
        
        # We will track adverse metrics specifically for this episode
        records.append({
            "scenario_id": scenario_id,
            "run_id": run_id,
            "robot_id": r_id,
            "task_id": t_id,
            "features": features
        })
        
    # Run planning for all
    for r_id in robots:
        t_id = global_state.robot_tasks.get(r_id)
        if t_id:
            await run_planning(r_id, t_id)
            
    # Run simulation
    sim_task = asyncio.create_task(simulator.run())
    await asyncio.sleep(0.01) # Allow it to run for a bit in simulation time
    simulator.is_running = False
    await sim_task
    
    # Determine labels based on metrics
    m = metrics_tracker.get_metrics()
    
    # We can also check if the specific robot ended up with battery < 20 or failed
    for rec in records:
        r_id = rec["robot_id"]
        rob = global_state.get_robot(r_id)
        
        risk = 0
        risk_reason = "NONE"
        
        if rob and rob.status == "FAILED":
            risk = 1
            risk_reason = "ROBOT_FAILURE"
        elif rob and rob.battery < 20.0:
            risk = 1
            risk_reason = "EMERGENCY_CHARGE"
        elif m["deadlocks_detected"] > 0:
            risk = 1
            risk_reason = "DEADLOCK"
        elif m["collision_count"] > 0:
            risk = 1
            risk_reason = "COLLISION"
        elif m["failed_tasks"] > 0:
            risk = 1
            risk_reason = "PATH_FAILURE"
            
        rec["label"] = risk
        rec["risk_reason"] = risk_reason
        
    return records

async def generate_dataset(num_samples=1500):
    print("Generating dataset...")
    os.makedirs("data", exist_ok=True)
    all_records = []
    
    run_id = 1
    seed = 42
    # Increase to 6000 samples for better distribution
    while len(all_records) < num_samples:
        # Increase number of tasks significantly in some runs to cause deadlocks/congestion
        n_tasks = random.randint(2, 12) if random.random() < 0.3 else random.randint(2, 6)
        recs = await generate_episode(seed, run_id, num_robots=random.randint(2, 6), num_tasks=n_tasks)
        all_records.extend(recs)
        seed += 1
        run_id += 1
        if seed % 50 == 0:
            print(f"  Generated {len(all_records)} samples...")
            
    # Save to CSV
    if not all_records:
        return
        
    keys = ["scenario_id", "run_id", "robot_id", "task_id"]
    keys.extend(list(all_records[0]["features"].keys()))
    keys.extend(["risk", "risk_reason"])
    
    with open("data/risk_dataset.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for rec in all_records:
            row = rec["features"].copy()
            row["scenario_id"] = rec["scenario_id"]
            row["run_id"] = rec["run_id"]
            row["robot_id"] = rec["robot_id"]
            row["task_id"] = rec["task_id"]
            row["risk"] = rec["label"]
            row["risk_reason"] = rec["risk_reason"]
            writer.writerow(row)
            
    print(f"Dataset generation complete. Saved {len(all_records)} records to data/risk_dataset.csv.")

if __name__ == "__main__":
    asyncio.run(generate_dataset(6000))
