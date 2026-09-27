from typing import Dict, List, Tuple

class ReservationManager:
    def __init__(self):
        # (node_id, time_step) -> robot_id
        self.vertex_reservations: Dict[Tuple[str, int], str] = {}
        
        # ((node_u, node_v), time_step) -> robot_id
        # This represents a robot traversing from u to v starting at time_step and arriving at time_step + 1
        self.edge_reservations: Dict[Tuple[Tuple[str, str], int], str] = {}

    def reset(self):
        self.vertex_reservations.clear()
        self.edge_reservations.clear()

    def reserve_path(self, robot_id: str, trajectory: List[Dict]):
        """
        trajectory: [{'node_id': str, 'time_step': int}]
        """
        for i in range(len(trajectory)):
            step = trajectory[i]
            node_id = step['node_id']
            t = step['time_step']
            
            # Reserve vertex
            self.vertex_reservations[(node_id, t)] = robot_id
            
            # Reserve edge if not the last step
            if i < len(trajectory) - 1:
                next_step = trajectory[i+1]
                next_node = next_step['node_id']
                if next_node != node_id: # Not waiting
                    self.edge_reservations[((node_id, next_node), t)] = robot_id

    def release_path(self, robot_id: str):
        # Remove all reservations for this robot
        self.vertex_reservations = {k: v for k, v in self.vertex_reservations.items() if v != robot_id}
        self.edge_reservations = {k: v for k, v in self.edge_reservations.items() if v != robot_id}

    def check_vertex_conflict(self, node_id: str, time_step: int) -> str:
        """Returns robot_id if conflict, else None"""
        return self.vertex_reservations.get((node_id, time_step))

    def check_edge_swap_conflict(self, node_u: str, node_v: str, time_step: int) -> str:
        """
        Edge swap conflict occurs if another robot travels from v to u at the exact same time_step.
        Returns robot_id if conflict, else None.
        """
        return self.edge_reservations.get(((node_v, node_u), time_step))

reservation_manager = ReservationManager()
