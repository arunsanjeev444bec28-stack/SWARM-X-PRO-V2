from __future__ import annotations

from dataclasses import dataclass, field
from time import time
from typing import Any, Dict, List, Optional


@dataclass
class MessageEnvelope:
    """Shared message envelope for peer-to-peer robot communication."""

    msg_type: str
    sender_id: str
    seq: int
    timestamp: float
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": self.msg_type,
            "sender_id": self.sender_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MessageEnvelope":
        return cls(
            msg_type=str(raw.get("msg_type", "UNKNOWN")),
            sender_id=str(raw.get("sender_id", "")),
            seq=int(raw.get("seq", 0)),
            timestamp=float(raw.get("timestamp", time())),
            payload=dict(raw.get("payload", {}) or {}),
        )


def build_heartbeat(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="HEARTBEAT",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_state_update(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="STATE_UPDATE",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_task_announce(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="TASK_ANNOUNCE",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_bid(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="BID",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_winner_claim(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="WINNER_CLAIM",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_intent(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="INTENT",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )


def build_task_reopen(robot_id: str, seq: int, payload: Optional[Dict[str, Any]] = None) -> MessageEnvelope:
    return MessageEnvelope(
        msg_type="TASK_REOPEN",
        sender_id=robot_id,
        seq=seq,
        timestamp=time(),
        payload=payload or {},
    )
