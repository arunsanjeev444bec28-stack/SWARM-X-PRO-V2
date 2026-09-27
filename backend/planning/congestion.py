import random
from core.state import global_state
from planning.astar import planner
from evaluation.metrics import metrics_tracker
from api.websocket import manager

async def calculate_congestion(trials: int = 300):
    all_nodes = global_state.get_all_nodes()
    if len(all_nodes) < 2:
        return
        
    node_ids = [n.node_id for n in all_nodes]
    traversals = {n: 0 for n in node_ids}
    
    # We will run simple unconstrained A* 
    # to estimate where traffic concentrates.
    for _ in range(trials):
        start = random.choice(node_ids)
        goal = random.choice(node_ids)
        while goal == start:
            goal = random.choice(node_ids)
            
        path = planner._plan_unconstrained(start, goal)
        for node_id in path:
            traversals[node_id] += 1
            
    # Calculate probabilities
    congested_count = 0
    max_prob = 0.0
    for node_id, count in traversals.items():
        prob = count / trials
        global_state.congestion_map[node_id] = prob
        if prob > max_prob:
            max_prob = prob
        if prob > 0.30:
            congested_count += 1
            
    metrics_tracker.congestion_probability = max_prob
    metrics_tracker.congested_nodes = congested_count
    
    # We broadcast an event
    await manager.broadcast({
        "event": "CONGESTION_UPDATED",
        "congested_nodes": congested_count,
        "max_probability": max_prob
    })
