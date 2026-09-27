from core.state import global_state
from models.schemas import AllocationResponse, Task, Robot
from intelligence.inference import predict_risk
from intelligence.features import extract_features
from edge_agents.coordination.cbaa import LocalCBAA, DEFAULT_CBAA_WEIGHTS, normalize_parameter
import math

class Allocator:
    """Task allocator that uses the authoritative LocalCBAA coordination engine from edge_agents."""

    def __init__(self):
        # Authoritative CBAA engine
        self.local_cbaa = LocalCBAA()
        self.weights = self.local_cbaa.weights
        
        # Compatibility aliases for endpoints and tests
        self.wd = self.weights["distance"]
        self.wt_time = self.weights["travel_time"]
        self.wc = self.weights["congestion"]
        self.wa = self.weights["availability"]
        self.wl = 0.0  # Workload removed completely from CBAA bid calculation
        self.we = 0.0  # Energy removed from CBAA bid calculation
        self.wt = 0.0  # Temperature removed from CBAA bid calculation
        self.wm = 0.0  # Makespan impact subsumed by travel_time
        self.wp = 0.0  # Priority handled as task arbitration factor
        self.risk_weight = 0.0 # Default ML risk weight (Phase 4)

    def filter_feasible_robots(self, task: Task) -> list[Robot]:
        feasible = []
        reserve_threshold = 5.0
        
        for robot in global_state.get_all_robots():
            if robot.status not in ["IDLE", "AVAILABLE"] and global_state.robot_tasks.get(robot.robot_id) != task.task_id:
                continue
            if robot.status in ["FAILED", "DEAD"]:
                continue
            if getattr(robot, 'health', 100.0) < 30.0:
                continue
            battery_after = robot.battery - task.energy_requirement
            if battery_after >= reserve_threshold:
                feasible.append(robot)
                
        return feasible

    def _extract_robot_metrics(self, robot: Robot, task: Task) -> dict:
        r_node = global_state.get_node(robot.node_id)
        t_node = global_state.get_node(task.pickup_node)
        
        if r_node and t_node:
            distance = abs(r_node.x - t_node.x) + abs(r_node.y - t_node.y)
        else:
            distance = 1000.0
            
        travel_time = distance / 1.0  # nominal speed 1.0 m/s
        congestion = float(global_state.congestion_map.get(task.pickup_node, 0.0))
        is_healthy = getattr(robot, 'health', 100.0) >= 30.0
        is_ready = (robot.status in ["IDLE", "AVAILABLE"] or global_state.robot_tasks.get(robot.robot_id) == task.task_id) and robot.status not in ["FAILED", "DEAD"]
        availability = 1.0 if (is_ready and is_healthy) else 0.0

        return {
            "robot_id": robot.robot_id,
            "distance": distance,
            "travel_time": travel_time,
            "congestion": congestion,
            "availability": availability,
            "status": robot.status,
            "health": getattr(robot, 'health', 100.0),
            "battery": robot.battery,
        }

    def calculate_bid(self, robot: Robot, task: Task) -> float:
        metrics = self._extract_robot_metrics(robot, task)
        # Weighted raw estimate without energy and without workload
        return (
            self.weights["distance"] * metrics["distance"]
            + self.weights["travel_time"] * metrics["travel_time"]
            + self.weights["congestion"] * metrics["congestion"]
            + self.weights["availability"] * (1.0 - metrics["availability"])
        )
        
    def calculate_bid_with_risk(self, robot: Robot, task: Task) -> dict:
        metrics = self._extract_robot_metrics(robot, task)
        base_bid = self.calculate_bid(robot, task)
        
        features = extract_features(robot.robot_id, task.task_id)
        risk_info = predict_risk(features)
        risk_prob = risk_info.get("risk_probability", 0.0)
        risk_penalty = self.risk_weight * risk_prob
        final_bid = base_bid + risk_penalty
        
        return {
            "robot_id": robot.robot_id,
            "distance": metrics["distance"],
            "travel_time": metrics["travel_time"],
            "congestion": metrics["congestion"],
            "availability": metrics["availability"],
            "base_bid": base_bid,
            "risk_probability": risk_prob,
            "risk_penalty": risk_penalty,
            "final_bid": final_bid,
            "total_bid": final_bid,
            "weights": dict(self.weights),
        }

    def allocate_task(self, task_id: str) -> AllocationResponse:
        task = global_state.get_task(task_id)
        if not task:
            return AllocationResponse(
                task_id=task_id, winner=None, winning_bid=None, selection_rule="MINIMUM VALID BID", feasible_robots=[], bids={}, reason="Task not found"
            )
            
        all_robots = global_state.get_all_robots()
        ineligible = {}
        raw_bids = {}
        feasible_robot_ids = []

        for robot in all_robots:
            metrics = self._extract_robot_metrics(robot, task)
            raw_bids[robot.robot_id] = metrics
            
            # Check feasibility
            if robot.status in ["FAILED", "DEAD"]:
                ineligible[robot.robot_id] = f"robot failed / dead (status={robot.status})"
            elif robot.status not in ["IDLE", "AVAILABLE"] and global_state.robot_tasks.get(robot.robot_id) != task_id:
                ineligible[robot.robot_id] = f"unavailable (status={robot.status})"
            elif getattr(robot, 'health', 100.0) < 30.0:
                ineligible[robot.robot_id] = "failed health (below 30.0 threshold)"
            elif robot.battery - task.energy_requirement < 5.0:
                ineligible[robot.robot_id] = "insufficient battery (< 5.0% reserve)"
            else:
                feasible_robot_ids.append(robot.robot_id)

        # Delegate to authoritative LocalCBAA engine
        cbaa_res = self.local_cbaa.normalize_and_rank_bids(
            raw_bids=raw_bids,
            ineligible_robots=ineligible,
            task_id=task_id,
        )

        # If risk weight is enabled (Phase 4 ML), apply it
        if self.risk_weight > 0.0:
            for rid in feasible_robot_ids:
                if rid in cbaa_res.bids:
                    features = extract_features(rid, task.task_id)
                    risk_info = predict_risk(features)
                    risk_prob = risk_info.get("risk_probability", 0.0)
                    risk_penalty = self.risk_weight * risk_prob
                    cbaa_res.bids[rid]["risk_probability"] = risk_prob
                    cbaa_res.bids[rid]["risk_penalty"] = risk_penalty
                    cbaa_res.bids[rid]["total_bid"] += risk_penalty
                    cbaa_res.bids[rid]["final_bid"] += risk_penalty
            # Re-rank feasible candidates
            valid_candidates = {rid: b for rid, b in cbaa_res.bids.items() if b.get("is_valid", False)}
            if valid_candidates:
                new_winner = min(valid_candidates, key=lambda rid: (valid_candidates[rid]["total_bid"], rid))
                cbaa_res.winner = new_winner
                cbaa_res.winning_bid = valid_candidates[new_winner]["total_bid"]
                for rid, b in cbaa_res.bids.items():
                    b["winner"] = (rid == new_winner)
                    if rid == new_winner:
                        b["status"] = "WINNER"

        winner_id = cbaa_res.winner
        if winner_id:
            from evaluation.metrics import metrics_tracker
            winner_robot = global_state.get_robot(winner_id)
            if winner_robot:
                winner_robot.status = "ASSIGNED"
                global_state.robot_tasks[winner_id] = task_id
                metrics_tracker.allocation_success += 1
            
            result = AllocationResponse(
                task_id=task_id, 
                winner=winner_id, 
                winning_bid=cbaa_res.winning_bid,
                selection_rule="MINIMUM VALID BID",
                feasible_robots=feasible_robot_ids, 
                bids=cbaa_res.bids, 
                reason=cbaa_res.reason,
                ineligible_robots=ineligible
            )
            global_state.allocations.append(result.model_dump())
            return result
            
        result = AllocationResponse(
            task_id=task_id, 
            winner=None, 
            winning_bid=None, 
            selection_rule="MINIMUM VALID BID", 
            feasible_robots=[], 
            bids=cbaa_res.bids, 
            reason="No feasible robots found",
            ineligible_robots=ineligible
        )
        global_state.allocations.append(result.model_dump())
        return result

allocator = Allocator()
