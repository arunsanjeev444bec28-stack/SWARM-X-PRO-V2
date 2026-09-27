import math
from core.state import global_state

def extract_features(robot_id: str, task_id: str) -> dict:
    robot = global_state.get_robot(robot_id)
    task = global_state.get_task(task_id)
    
    if not robot or not task:
        return {}

    # Calculate basic Manhattan distances
    pickup_node = global_state.nodes.get(task.pickup_node)
    dispatch_node = global_state.nodes.get(task.dispatch_node)
    robot_node = global_state.nodes.get(robot.node_id)
    
    dist_to_pickup = 0.0
    dist_to_dispatch = 0.0
    path_length = 0.0
    
    if robot_node and pickup_node and dispatch_node:
        dist_to_pickup = abs(robot_node.x - pickup_node.x) + abs(robot_node.y - pickup_node.y)
        dist_to_dispatch = abs(pickup_node.x - dispatch_node.x) + abs(pickup_node.y - dispatch_node.y)
        path_length = dist_to_pickup + dist_to_dispatch

    # Priority mapping
    priority_map = {"LOW": 1.0, "NORMAL": 2.0, "HIGH": 3.0, "CRITICAL": 4.0}
    task_priority = priority_map.get(task.priority, 2.0)

    # Congestion probability (global average from metrics tracker)
    from evaluation.metrics import metrics_tracker
    congestion_prob = metrics_tracker.congestion_probability

    # Node health (min over pickup and dispatch)
    h_pickup = pickup_node.health if pickup_node else 100.0
    h_dispatch = dispatch_node.health if dispatch_node else 100.0
    node_health = min(h_pickup, h_dispatch)

    # Nearby robots (within distance 5)
    nearby_robots = 0
    if robot_node:
        for r in global_state.get_all_robots():
            if r.robot_id != robot_id:
                rn = global_state.nodes.get(r.node_id)
                if rn:
                    d = abs(robot_node.x - rn.x) + abs(robot_node.y - rn.y)
                    if d <= 5.0:
                        nearby_robots += 1

    # Remaining deadline
    # Assuming simulator current_time_step is global_state.simulator_time, but we don't have it directly in global_state.
    # We can default to the deadline itself as an estimate of total allowable time if we don't track start time carefully here,
    # or we can just use task.deadline.
    remaining_deadline = task.deadline

    return {
        "battery": float(robot.battery),
        "temperature": float(robot.temperature),
        "load": float(robot.load),
        "robot_health": float(robot.health),
        "task_priority": float(task_priority),
        "task_urgency": float(task.urgency),
        "distance_to_pickup": float(dist_to_pickup),
        "distance_to_dispatch": float(dist_to_dispatch),
        "estimated_energy": float(task.energy_requirement),
        "current_workload": float(1.0 if robot.status == "ASSIGNED" else 0.0),
        "path_length": float(path_length),
        "congestion_probability": float(congestion_prob),
        "reservation_conflict_count": float(0.0), # Estimated feature
        "nearby_robot_count": float(nearby_robots),
        "node_health": float(node_health),
        "dynamic_obstacle_present": float(1.0 if len(global_state.dynamic_obstacles) > 0 else 0.0),
        "deadline": float(task.deadline),
        "remaining_deadline": float(remaining_deadline),
        "replan_count": float(0.0) # Before planning
    }
