"""Default configuration for edge-agent local operation.

These values are intentionally conservative and can be tuned later to match the
backend warehouse configuration or a future CoppeliaSim setup.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EdgeAgentConfig:
    heartbeat_hz: float = 5.0
    stale_timeout_seconds: float = 0.6
    dead_timeout_seconds: float = 2.0
    robot_id: str = "R1"
    local_port: int = 5555
    tcp_endpoints: dict = None
    bid_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "distance": 1.0,
            "travel_time": 0.8,
            "battery": 0.3,
            "availability": 0.4,
            "congestion": 0.25,
            "priority": 0.45,
        }
    )

    def __post_init__(self):
        if self.tcp_endpoints is None:
            object.__setattr__(
                self,
                "tcp_endpoints",
                {
                    "R1": "tcp://127.0.0.1:5555",
                    "R2": "tcp://127.0.0.1:5556",
                    "R3": "tcp://127.0.0.1:5557",
                    "R4": "tcp://127.0.0.1:5558",
                },
            )


EDGE_AGENT_CONFIG = EdgeAgentConfig()
