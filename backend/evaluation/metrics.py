class MetricsTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.allocation_success = 0
        self.total_distance = 0.0
        self.replan_count = 0
        self.collision_count = 0
        self.alternate_path_count = 0
        self.wait_fallback = 0
        self.reservation_conflicts = 0
        self.task_completion_times = []
        self.pickup_events = 0
        self.dispatch_events = 0
        
        # Phase 2 metrics
        self.battery_consumption = 0.0
        self.charging_events = 0
        self.emergency_charges = 0
        self.node_failures = 0
        self.node_degraded_events = 0
        self.congestion_probability = 0.0
        self.congested_nodes = 0
        self.dynamic_obstacle_events = 0
        self.obstacle_replans = 0
        self.obstacle_recovery_success = 0
        self.obstacle_failure = 0
        self.robot_failures = 0
        self.tasks_reauctioned = 0
        self.successful_reassignments = 0
        self.failed_reassignments = 0
        self.failure_recovery_time = 0.0
        
        # Deadlocks
        self.deadlocks_detected = 0
        self.deadlocks_recovered = 0
        self.deadlock_recovery_failures = 0
        self.deadlock_recovery_attempts = 0
        self.deadlock_recovery_time = 0.0

    def get_metrics(self):
        return {
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "allocation_success": self.allocation_success,
            "total_distance": self.total_distance,
            "replan_count": self.replan_count,
            "alternate_path_count": self.alternate_path_count,
            "wait_fallback": self.wait_fallback,
            "reservation_conflicts": self.reservation_conflicts,
            "collision_count": self.collision_count,
            "task_completion_times": self.task_completion_times,
            "fleet_makespan": max(self.task_completion_times) if self.task_completion_times else 0,
            "pickup_events": self.pickup_events,
            "dispatch_events": self.dispatch_events,
            "battery_consumption": self.battery_consumption,
            "charging_events": self.charging_events,
            "emergency_charges": self.emergency_charges,
            "node_failures": self.node_failures,
            "node_degraded_events": self.node_degraded_events,
            "congestion_probability": self.congestion_probability,
            "congested_nodes": self.congested_nodes,
            "dynamic_obstacle_events": self.dynamic_obstacle_events,
            "obstacle_replans": self.obstacle_replans,
            "obstacle_recovery_success": self.obstacle_recovery_success,
            "obstacle_failure": self.obstacle_failure,
            "robot_failures": self.robot_failures,
            "tasks_reauctioned": self.tasks_reauctioned,
            "successful_reassignments": self.successful_reassignments,
            "failed_reassignments": self.failed_reassignments,
            "failure_recovery_time": self.failure_recovery_time,
            "deadlocks_detected": self.deadlocks_detected,
            "deadlocks_recovered": self.deadlocks_recovered,
            "deadlock_recovery_failures": self.deadlock_recovery_failures,
            "deadlock_recovery_attempts": self.deadlock_recovery_attempts,
            "deadlock_recovery_time": self.deadlock_recovery_time
        }

metrics_tracker = MetricsTracker()
