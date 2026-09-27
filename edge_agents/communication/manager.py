from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

import zmq

from edge_agents.communication.protocol import MessageEnvelope


class EnvelopeValidationError(ValueError):
    pass


@dataclass
class NeighborStatus:
    robot_id: str
    last_seen: float
    last_sequence: int = 0
    connection_state: str = "ONLINE"


class SequenceTracker:
    """Reject duplicates and older out-of-order sequences per sender."""

    def __init__(self):
        self._last_sequence: Dict[str, int] = {}

    def accept(self, sender_id: str, seq: int) -> bool:
        if sender_id not in self._last_sequence:
            self._last_sequence[sender_id] = seq
            return True

        last_seq = self._last_sequence[sender_id]
        if seq == last_seq:
            return False
        if seq < last_seq:
            return False
        self._last_sequence[sender_id] = seq
        return True

    def get_last_sequence(self, sender_id: str) -> int:
        return self._last_sequence.get(sender_id, 0)

    def reset(self) -> None:
        self._last_sequence.clear()


class RobotCommunicationManager:
    """Actual peer-to-peer transport manager using ZeroMQ PUB/SUB over TCP."""

    def __init__(
        self,
        robot_id: str,
        peers: Optional[Iterable[str]] = None,
        pub_endpoint: Optional[str] = None,
        sub_endpoints: Optional[Iterable[str]] = None,
        heartbeat_hz: float = 5.0,
        stale_timeout_seconds: float = 0.6,
        dead_timeout_seconds: float = 2.0,
    ):
        self.robot_id = robot_id
        self.peer_ids: Set[str] = set(peers or [])
        self.pub_endpoint = pub_endpoint or self._default_pub_endpoint(robot_id)
        self.sub_endpoints: List[str] = list(sub_endpoints or [])
        self.heartbeat_hz = float(heartbeat_hz)
        self.stale_timeout_seconds = float(stale_timeout_seconds)
        self.dead_timeout_seconds = float(dead_timeout_seconds)

        self.context: Optional[zmq.Context] = None
        self.pub_socket: Optional[zmq.Socket] = None
        self.sub_socket: Optional[zmq.Socket] = None

        self.sequence_tracker = SequenceTracker()
        self.neighbor_status: Dict[str, NeighborStatus] = {}
        self._lock = threading.Lock()
        self._sequence = 0

    @staticmethod
    def _default_pub_endpoint(robot_id: str) -> str:
        mapping = {
            "R1": "tcp://127.0.0.1:55501",
            "R2": "tcp://127.0.0.1:55502",
            "R3": "tcp://127.0.0.1:55503",
            "R4": "tcp://127.0.0.1:55504",
        }
        return mapping.get(robot_id, "tcp://127.0.0.1:55505")

    def set_peer_endpoints(self, peer_endpoints: Dict[str, str]) -> None:
        for peer_id, endpoint in peer_endpoints.items():
            self.peer_ids.add(peer_id)
        self.sub_endpoints = list(peer_endpoints.values())

    def start(self) -> None:
        if self.context is not None:
            return

        self.context = zmq.Context.instance()
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(self.pub_endpoint)

        self.sub_socket = self.context.socket(zmq.SUB)
        self.sub_socket.setsockopt(zmq.SUBSCRIBE, b"")
        for endpoint in self.sub_endpoints:
            self.sub_socket.connect(endpoint)

    def publish_message(self, msg_type: str, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
        if self.pub_socket is None:
            raise RuntimeError("Communication manager has not been started")

        self._sequence += 1
        envelope = MessageEnvelope(
            msg_type=msg_type,
            sender_id=self.robot_id,
            seq=self._sequence,
            timestamp=time.time(),
            payload=payload or {},
        )
        self.pub_socket.send_multipart([
            self.robot_id.encode("utf-8"),
            json.dumps(envelope.to_dict(), separators=(",", ":")).encode("utf-8"),
        ])
        return envelope

    def receive_messages(self, timeout_ms: int = 100) -> List[MessageEnvelope]:
        if self.sub_socket is None:
            return []

        envelopes: List[MessageEnvelope] = []
        poller = zmq.Poller()
        poller.register(self.sub_socket, zmq.POLLIN)

        socks = dict(poller.poll(timeout_ms))
        if self.sub_socket not in socks:
            return []

        while True:
            try:
                topic, raw = self.sub_socket.recv_multipart(zmq.NOBLOCK)
            except zmq.Again:
                break
            except ValueError:
                break
            try:
                message = self._decode_message(raw)
            except (TypeError, ValueError, json.JSONDecodeError, EnvelopeValidationError):
                continue
            if not message:
                continue
            if message.sender_id == self.robot_id:
                continue
            envelopes.append(message)
            self._update_neighbor_from_message(message)
            if self._is_duplicate(message):
                continue
        return envelopes

    def _decode_message(self, raw: bytes) -> MessageEnvelope:
        if isinstance(raw, (bytes, bytearray)):
            obj = json.loads(raw.decode("utf-8"))
        else:
            obj = json.loads(raw)
        return MessageEnvelope.from_dict(obj)

    def _is_duplicate(self, message: MessageEnvelope) -> bool:
        return not self.sequence_tracker.accept(message.sender_id, message.seq)

    def _update_neighbor_from_message(self, message: MessageEnvelope) -> None:
        neighbor = self.neighbor_status.setdefault(
            message.sender_id,
            NeighborStatus(robot_id=message.sender_id, last_seen=time.time()),
        )
        neighbor.last_seen = time.time()
        neighbor.last_sequence = max(neighbor.last_sequence, message.seq)
        neighbor.connection_state = "ONLINE"

    def validate_envelope(self, envelope: Dict[str, Any]) -> MessageEnvelope:
        if not isinstance(envelope, dict):
            raise EnvelopeValidationError("Message is not a dict")
        required = {"msg_type", "sender_id", "seq", "timestamp", "payload"}
        if not required.issubset(envelope.keys()):
            raise EnvelopeValidationError("Missing required envelope keys")
        if envelope["msg_type"] not in {"HEARTBEAT", "STATE_UPDATE", "TASK_ANNOUNCE", "BID", "WINNER_CLAIM", "INTENT", "OBSTACLE_REPORT", "TASK_REOPEN"}:
            raise EnvelopeValidationError("Unsupported msg_type")
        if not isinstance(envelope["sender_id"], str) or not envelope["sender_id"]:
            raise EnvelopeValidationError("sender_id must be a non-empty string")
        if not isinstance(envelope["payload"], dict):
            raise EnvelopeValidationError("payload must be a dict")
        try:
            seq = int(envelope["seq"])
        except (TypeError, ValueError):
            raise EnvelopeValidationError("invalid seq") from None
        try:
            float(envelope["timestamp"])
        except (TypeError, ValueError):
            raise EnvelopeValidationError("invalid timestamp") from None
        return MessageEnvelope.from_dict(envelope)

    def assess_neighbor_state(self, now: Optional[float] = None) -> Dict[str, str]:
        current_time = now if now is not None else time.time()
        states: Dict[str, str] = {}
        for robot_id, neighbor in self.neighbor_status.items():
            delta = current_time - neighbor.last_seen
            if delta > self.dead_timeout_seconds:
                neighbor.connection_state = "DEAD"
            elif delta > self.stale_timeout_seconds:
                neighbor.connection_state = "STALE"
            else:
                neighbor.connection_state = "ONLINE"
            states[robot_id] = neighbor.connection_state
        return states

    def close(self) -> None:
        if self.sub_socket is not None:
            self.sub_socket.close()
        if self.pub_socket is not None:
            self.pub_socket.close()
        if self.context is not None:
            self.context.term()
        self.sub_socket = None
        self.pub_socket = None
        self.context = None


def build_topology() -> Dict[str, List[str]]:
    return {
        "R1": ["R2", "R3", "R4"],
        "R2": ["R1", "R3", "R4"],
        "R3": ["R1", "R2", "R4"],
        "R4": ["R1", "R2", "R3"],
    }
