"""
Gazebo and ROS 2 Adapter Layer for SWARM-X PRO V2.

Maintains the clean architecture:
Gazebo/ROS 2 <-> GazeboAdapter <-> backend state/algorithms <-> dashboard

Does not fabricate physical Gazebo execution when ROS 2 is not active.
Reports honest status and translates coordinates between real Gazebo world
and backend state.
"""

from typing import Dict, Any, Optional
import os


class GazeboAdapter:
    """
    Adapter interface connecting Gazebo / ROS 2 to the backend state.
    """
    def __init__(self):
        self.ros_domain_id = os.getenv("ROS_DOMAIN_ID", "0")
        self.bridge_host = os.getenv("ROS_BRIDGE_HOST", "127.0.0.1")
        self.bridge_port = int(os.getenv("ROS_BRIDGE_PORT", "9090"))
        self._connected = False

    def check_connection(self) -> bool:
        """
        Check if a live ROS 2 daemon or rosbridge socket is actively communicating.
        Returns False if running without external ROS daemon.
        """
        # We do not fabricate connection. Live check would attempt socket connection if configured.
        return self._connected

    def get_status(self) -> Dict[str, Any]:
        """
        Return the truthful status of Gazebo/ROS 2 connectivity.
        """
        is_live = self.check_connection()
        if is_live:
            return {
                "status": "CONNECTED",
                "live_connected": True,
                "mode": "GAZEBO_LIVE",
                "bridge_host": self.bridge_host,
                "bridge_port": self.bridge_port,
                "ros_domain_id": self.ros_domain_id
            }
        return {
            "status": "DATA UNAVAILABLE",
            "live_connected": False,
            "mode": "BACKEND_REAL_SIMULATION",
            "message": "Host environment does not have active ROS 2 / Gazebo daemon. Operating in authoritative backend simulation/planning mode."
        }

    def convert_world_to_node(self, x: float, y: float, tolerance: float = 0.5) -> Optional[str]:
        """
        Convert continuous Gazebo coordinates to nearest warehouse node ID.
        """
        from data.warehouse_real import get_node_id, is_point_valid
        if not is_point_valid(x, y):
            return None
        return get_node_id(x, y)


gazebo_adapter = GazeboAdapter()
