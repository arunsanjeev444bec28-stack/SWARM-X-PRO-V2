import heapq
import math
from typing import List

from core.state import global_state
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from models.schemas import TrajectoryStep, PlanningResponse


class Planner:

    def __init__(self):
        # Real warehouse movement model
        self.robot_speed_mps = 1.0
        self.time_step_seconds = 1.0

    def distance(self, u_id: str, v_id: str) -> float:
        u = global_state.get_node(u_id)
        v = global_state.get_node(v_id)

        if not u or not v:
            return float("inf")

        return math.hypot(
            v.x - u.x,
            v.y - u.y
        )

    def heuristic(self, u_id: str, v_id: str) -> float:
        return self.distance(u_id, v_id)

    def _plan_unconstrained(
        self,
        start_id: str,
        goal_id: str
    ) -> List[str]:

        if start_id == goal_id:
            return [start_id]

        open_set = []

        heapq.heappush(
            open_set,
            (
                self.heuristic(start_id, goal_id),
                0.0,
                start_id,
                [start_id]
            )
        )

        best_g = {
            start_id: 0.0
        }

        while open_set:

            f, g, curr_id, path = heapq.heappop(open_set)

            if curr_id == goal_id:
                return path

            if g > best_g.get(
                curr_id,
                float("inf")
            ):
                continue

            curr_node = global_state.get_node(
                curr_id
            )

            if not curr_node:
                continue

            for next_id in curr_node.neighbors:

                next_node = global_state.get_node(
                    next_id
                )

                if not next_node:
                    continue

                if next_node.health < 30.0:
                    continue

                edge_distance = self.distance(
                    curr_id,
                    next_id
                )

                if not math.isfinite(
                    edge_distance
                ):
                    continue

                new_g = g + edge_distance

                if new_g >= best_g.get(
                    next_id,
                    float("inf")
                ):
                    continue

                best_g[next_id] = new_g

                new_f = (
                    new_g
                    + self.heuristic(
                        next_id,
                        goal_id
                    )
                )

                heapq.heappush(
                    open_set,
                    (
                        new_f,
                        new_g,
                        next_id,
                        path + [next_id]
                    )
                )

        return []

    def plan_time_space_astar(
        self,
        robot_id: str,
        start_id: str,
        goal_id: str,
        start_time: int
    ) -> PlanningResponse:

        if start_id == goal_id:

            trajectory = [
                TrajectoryStep(
                    node_id=start_id,
                    time_step=start_time
                )
            ]

            return PlanningResponse(
                robot_id=robot_id,
                task_id=global_state.robot_tasks.get(
                    robot_id,
                    ""
                ),
                path=[start_id],
                trajectory=trajectory,
                distance=0.0,
                estimated_time=0.0,
                replanned=False,
                conflict_with=None,
                conflict_node=None,
                conflict_time_step=None,
                unconstrained_path=[start_id]
            )

        open_set = []

        start_h = self.heuristic(
            start_id,
            goal_id
        )

        heapq.heappush(
            open_set,
            (
                start_h,
                0.0,
                start_time,
                start_id,
                [start_id],
                [
                    TrajectoryStep(
                        node_id=start_id,
                        time_step=start_time
                    )
                ]
            )
        )

        closed_set = set()
        best_g = {(start_id, start_time): 0.0}

        replanned = False
        conflict_with = None
        conflict_node = None
        conflict_time_step = None

        unconstrained_path = (
            self._plan_unconstrained(
                start_id,
                goal_id
            )
        )

        blocking_robots = set()

        while open_set:

            (
                f,
                g,
                t,
                curr_id,
                path,
                trajectory
            ) = heapq.heappop(open_set)

            if g > best_g.get((curr_id, t), float("inf")):
                continue

            if curr_id == goal_id:

                dist = 0.0
                unique_path = [path[0]]

                for i in range(
                    1,
                    len(path)
                ):

                    if path[i] != path[i - 1]:

                        dist += self.distance(
                            path[i - 1],
                            path[i]
                        )

                        unique_path.append(
                            path[i]
                        )

                reservation_manager.reserve_path(
                    robot_id,
                    [
                        {
                            "node_id": step.node_id,
                            "time_step": step.time_step
                        }
                        for step in trajectory
                    ]
                )

                ideal_path = (
                    self._plan_unconstrained(
                        start_id,
                        goal_id
                    )
                )

                has_wait = (
                    len(path)
                    > len(unique_path)
                )

                has_alternate = (
                    unique_path
                    != ideal_path
                )

                if replanned:

                    if has_alternate:
                        metrics_tracker.alternate_path_count += 1

                    if has_wait:
                        metrics_tracker.wait_fallback += 1

                movement_time = dist / self.robot_speed_mps
                wait_time = (len(path) - len(unique_path)) * self.time_step_seconds
                estimated_time = movement_time + wait_time

                return PlanningResponse(
                    robot_id=robot_id,
                    task_id=global_state.robot_tasks.get(
                        robot_id,
                        ""
                    ),
                    path=unique_path,
                    trajectory=trajectory,
                    distance=dist,
                    estimated_time=estimated_time,
                    replanned=replanned,
                    conflict_with=conflict_with,
                    conflict_node=conflict_node,
                    conflict_time_step=conflict_time_step,
                    unconstrained_path=unconstrained_path
                )

            state_tuple = (
                curr_id,
                t
            )

            if state_tuple in closed_set:
                continue

            closed_set.add(state_tuple)

            curr_node = global_state.get_node(
                curr_id
            )

            if not curr_node:
                continue

            # Move OR wait
            neighbors = list(
                curr_node.neighbors
            )

            if curr_id not in neighbors:
                neighbors.append(
                    curr_id
                )

            for next_id in neighbors:

                next_t = t + 1

                # Vertex conflict
                conflict_robot = (
                    reservation_manager
                    .check_vertex_conflict(
                        next_id,
                        next_t
                    )
                )

                if (
                    conflict_robot
                    and conflict_robot != robot_id
                ):

                    replanned = True

                    conflict_with = (
                        conflict_robot
                    )

                    conflict_node = next_id

                    conflict_time_step = (
                        next_t
                    )

                    metrics_tracker.reservation_conflicts += 1

                    blocking_robots.add(
                        conflict_robot
                    )

                    continue

                # Edge swap conflict
                if next_id != curr_id:

                    swap_robot = (
                        reservation_manager
                        .check_edge_swap_conflict(
                            curr_id,
                            next_id,
                            t
                        )
                    )

                    if (
                        swap_robot
                        and swap_robot != robot_id
                    ):

                        replanned = True

                        conflict_with = (
                            swap_robot
                        )

                        conflict_node = (
                            f"{curr_id}->{next_id}"
                        )

                        conflict_time_step = (
                            next_t
                        )

                        metrics_tracker.reservation_conflicts += 1

                        blocking_robots.add(
                            swap_robot
                        )

                        continue

                # Dynamic obstacle
                obs_expiration = (
                    global_state
                    .dynamic_obstacles
                    .get(next_id)
                )

                if (
                    obs_expiration
                    and next_t < obs_expiration
                ):
                    continue

                next_node = global_state.get_node(
                    next_id
                )

                if not next_node:
                    continue

                # Failed node
                if next_node.health < 30.0:
                    continue

                # Physical movement cost
                if next_id == curr_id:

                    edge_distance = 0.0

                    step_cost = (
                        self.time_step_seconds
                    )

                else:

                    edge_distance = self.distance(
                        curr_id,
                        next_id
                    )

                    if not math.isfinite(
                        edge_distance
                    ):
                        continue

                    step_cost = (
                        edge_distance /
                        self.robot_speed_mps
                    )

                # Degraded node
                if next_node.health < 70.0:
                    step_cost += 5.0

                # Congestion
                probability = (
                    global_state
                    .congestion_map
                    .get(
                        next_id,
                        0.0
                    )
                )

                if probability > 0.30:
                    step_cost += (
                        3.0 * probability
                    )

                new_g = g + step_cost

                new_h = self.heuristic(
                    next_id,
                    goal_id
                )

                new_f = (
                    new_g + new_h
                )

                new_path = (
                    path + [next_id]
                )

                new_traj = (
                    trajectory +
                    [
                        TrajectoryStep(
                            node_id=next_id,
                            time_step=next_t
                        )
                    ]
                )

                if len(new_path) > 300:
                    continue

                if new_g < best_g.get((next_id, next_t), float("inf")):
                    best_g[(next_id, next_t)] = new_g
                    heapq.heappush(
                        open_set,
                        (
                            new_f,
                            new_g,
                            next_t,
                            next_id,
                            new_path,
                            new_traj
                        )
                    )

        return PlanningResponse(
            robot_id=robot_id,
            task_id=global_state.robot_tasks.get(
                robot_id,
                ""
            ),
            path=[],
            trajectory=[],
            distance=0.0,
            estimated_time=0.0,
            replanned=replanned,
            blocking_robots=list(
                blocking_robots
            )
        )


planner = Planner()