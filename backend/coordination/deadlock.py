from typing import List, Dict, Set
from core.state import global_state

class DependencyGraph:
    def __init__(self):
        # adjacency list: robot_id -> set of robot_ids it is waiting on
        self.graph: Dict[str, Set[str]] = {}
        
    def clear(self):
        self.graph.clear()
        
    def add_dependency(self, robot_a: str, robot_b: str):
        if robot_a not in self.graph:
            self.graph[robot_a] = set()
        self.graph[robot_a].add(robot_b)
        
    def remove_dependency(self, robot_a: str, robot_b: str):
        if robot_a in self.graph and robot_b in self.graph[robot_a]:
            self.graph[robot_a].remove(robot_b)
            if not self.graph[robot_a]:
                del self.graph[robot_a]
                
    def get_dependencies(self, robot_id: str) -> List[str]:
        return list(self.graph.get(robot_id, []))
        
    def detect_cycles(self) -> List[List[str]]:
        """
        Returns a list of cycles (each cycle is a list of robot_ids).
        Uses DFS to find cycles.
        """
        cycles = []
        visited = set()
        path = []
        
        def dfs(node):
            if node in path:
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            if node in visited:
                return
                
            visited.add(node)
            path.append(node)
            
            for neighbor in self.graph.get(node, []):
                dfs(neighbor)
                
            path.pop()
            
        for node in self.graph:
            dfs(node)
            
        # Deduplicate cycles
        unique_cycles = []
        seen = set()
        for cycle in cycles:
            canon = tuple(sorted(set(cycle)))
            if canon not in seen:
                seen.add(canon)
                unique_cycles.append(cycle)
                
        return unique_cycles

    def has_cycle(self) -> bool:
        return len(self.detect_cycles()) > 0
        
    def select_yielding_robot(self, cycle: List[str]) -> str:
        """
        Deterministic selection:
        - lower task priority yields first
        - if equal priority, lower urgency yields
        - if equal, higher battery yields
        - if equal, higher robot ID yields
        """
        priority_map = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        
        candidates = []
        for r_id in cycle:
            if r_id not in global_state.robots:
                continue # Edge case
                
            robot = global_state.robots[r_id]
            task_id = global_state.robot_tasks.get(r_id)
            priority_val = 4
            urgency_val = 1.0
            
            if task_id and task_id in global_state.tasks:
                task = global_state.tasks[task_id]
                priority_val = priority_map.get(task.priority, 1)
                urgency_val = task.urgency
                
            # Tuples are sorted in ascending order.
            # We want:
            # 1. Lower priority first (ascending priority_val)
            # 2. Lower urgency first (ascending urgency_val)
            # 3. Higher battery first (descending battery -> ascending -battery)
            # 4. Higher robot ID first (descending ID -> ascending reverse string sorting, or just let python handle it)
            # Actually, standard python string comparison for IDs. To get higher ID first, we use reverse string comparison or just custom sorting.
            
            candidates.append((priority_val, urgency_val, -robot.battery, r_id))
            
        # Sort candidates
        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]), reverse=False)
        
        # But wait! For robot ID, we want higher ID first, so we should reverse the string comparison.
        # Since r_id is a string like "R1", "R2", we can just sort by reverse of r_id.
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        
        # Actually to break tie properly:
        def tie_breaker(c):
            return (c[0], c[1], c[2], c[3])
            
        candidates.sort(key=tie_breaker)
        # Wait, if all are equal, lower ID string will come first if we use c[3].
        # The rule says: "if equal, higher robot ID yields".
        # So we should sort by reverse of ID string for that tie-breaker.
        # Let's fix that.
        
        def final_tie_breaker(c):
            p_val, u_val, neg_bat, r_id = c
            return (p_val, u_val, neg_bat, r_id) # default
            
        # Re-write cleanly
        def get_sort_key(r_id: str):
            robot = global_state.get_robot(r_id)
            if not robot: return (99, 99.0, 0.0, r_id)
            
            task_id = global_state.robot_tasks.get(r_id)
            priority_val = 4
            urgency_val = 1.0
            if task_id:
                task = global_state.get_task(task_id)
                if task:
                    priority_val = priority_map.get(task.priority, 1)
                    urgency_val = task.urgency
                    
            # 1. Lower priority -> lower value
            # 2. Lower urgency -> lower value
            # 3. Higher battery -> lower negative value
            # 4. Higher robot ID -> sort descending by string logic? 
            # We can just return a tuple and sort. But to sort ID descending within the same tuple:
            # Since ID is a string, we can't easily negate it. We'll sort by the first 3 normally, then ID descending.
            return (priority_val, urgency_val, -robot.battery)

        # Sort first by the main metrics (ascending)
        cycle_unique = list(set(cycle))
        cycle_unique.sort(key=get_sort_key)
        
        # Resolve ties for ID manually:
        best_r_id = cycle_unique[0]
        best_key = get_sort_key(best_r_id)
        
        tied = [r for r in cycle_unique if get_sort_key(r) == best_key]
        if len(tied) > 1:
            # Higher robot ID yields (e.g. "R2" > "R1")
            tied.sort(reverse=True)
            return tied[0]
            
        return best_r_id

dependency_graph = DependencyGraph()

from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from api.websocket import manager

async def recover_deadlock(cycle: List[str]):
    import asyncio
    yield_r = dependency_graph.select_yielding_robot(cycle)
    
    await manager.broadcast({
        "event": "DEADLOCK_RECOVERY_STARTED",
        "robots": list(cycle),
        "yielding_robot": yield_r,
        "attempt": 1
    })
    
    # Release future reservations
    reservation_manager.release_path(yield_r)
    
    # We must trigger a replan for the yielding robot.
    from api.main import run_planning
    from simulation.engine import simulator
    
    task_id = global_state.robot_tasks.get(yield_r)
    if task_id:
        for attempt in range(1, 4):
            metrics_tracker.deadlock_recovery_attempts += 1
            
            # Broadcast attempt if > 1
            if attempt > 1:
                await manager.broadcast({
                    "event": "DEADLOCK_RECOVERY_STARTED",
                    "robots": list(cycle),
                    "yielding_robot": yield_r,
                    "attempt": attempt
                })
                
            # Replan yielding robot
            res = await run_planning(yield_r, task_id, simulator.current_time_step, is_recovery=True)
            if res.get("path"):
                # Successfully replanned yielding robot
                if yield_r in dependency_graph.graph:
                    del dependency_graph.graph[yield_r]
                    
                # verify cycle is removed
                if not dependency_graph.has_cycle():
                    metrics_tracker.deadlocks_recovered += 1
                    await manager.broadcast({
                        "event": "DEADLOCK_RECOVERED",
                        "robots": list(cycle),
                        "yielding_robot": yield_r,
                        "attempt": attempt
                    })
                    return True
            
            # If we failed, wait a bit to let other robots advance their trajectories (if they have any)
            await asyncio.sleep(0.5)
            
    metrics_tracker.deadlock_recovery_failures += 1
    await manager.broadcast({
        "event": "DEADLOCK_RECOVERY_FAILED",
        "robots": list(cycle),
        "yielding_robot": yield_r,
        "attempts": 3
    })
    return False
