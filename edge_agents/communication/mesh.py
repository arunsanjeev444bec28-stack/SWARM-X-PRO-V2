from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Dict, List, Optional, Set

try:  # pragma: no cover - optional dependency
    import zmq  # type: ignore
except Exception:  # pragma: no cover
    zmq = None

from edge_agents.communication.protocol import MessageEnvelope


@dataclass
class PeerConnectionState:
    peer_id: str
    last_seen: float
    status: str = "UNKNOWN"
    heartbeat_seq: int = 0
    last_message: Optional[MessageEnvelope] = None


class PeerMesh:
    """A peer-to-peer communication abstraction for the edge-agent layer.

    In the current environment the optional ZeroMQ dependency may be absent, so
    this mesh uses an in-process message bus for validation while still providing
    the same topology and message envelope semantics required by the design.
    """

    def __init__(self, robot_id: str, peers: Optional[List[str]] = None):
        self.robot_id = robot_id
        self.peers: Set[str] = set(peers or [])
        self._bus: Dict[str, List[MessageEnvelope]] = {}
        self._peer_state: Dict[str, PeerConnectionState] = {}
        self._zmq_context = None
        if zmq is not None:
            self._zmq_context = zmq.Context()

    def register_peer(self, peer_id: str) -> None:
        self.peers.add(peer_id)
        self._peer_state.setdefault(peer_id, PeerConnectionState(peer_id=peer_id, last_seen=time()))

    def send(self, recipient_id: str, message: MessageEnvelope) -> bool:
        if recipient_id not in self.peers:
            self.register_peer(recipient_id)
        self._bus.setdefault(recipient_id, []).append(message)
        self._peer_state.setdefault(recipient_id, PeerConnectionState(peer_id=recipient_id, last_seen=time()))
        self._peer_state[recipient_id].last_seen = time()
        self._peer_state[recipient_id].status = "ACTIVE"
        self._peer_state[recipient_id].last_message = message
        return True

    def receive(self, sender_id: str) -> Optional[MessageEnvelope]:
        inbox = self._bus.get(sender_id, [])
        if not inbox:
            return None
        return inbox.pop(0)

    def peer_status(self, peer_id: str) -> PeerConnectionState:
        return self._peer_state.setdefault(peer_id, PeerConnectionState(peer_id=peer_id, last_seen=time()))

    def snapshot(self) -> Dict[str, Any]:
        return {
            "robot_id": self.robot_id,
            "peers": sorted(self.peers),
            "peer_state": {
                peer_id: {
                    "last_seen": state.last_seen,
                    "status": state.status,
                    "heartbeat_seq": state.heartbeat_seq,
                }
                for peer_id, state in self._peer_state.items()
            },
        }


class ZeroMQPeerTopology:
    """Topology for the required local Mesh: R1↔R2, R1↔R3, R1↔R4, R2↔R3, R2↔R4, R3↔R4."""

    @staticmethod
    def build_topology() -> Dict[str, List[str]]:
        return {
            "R1": ["R2", "R3", "R4"],
            "R2": ["R1", "R3", "R4"],
            "R3": ["R1", "R2", "R4"],
            "R4": ["R1", "R2", "R3"],
        }
