"""Peer-to-peer communication primitives for the edge-agent layer."""

from .protocol import MessageEnvelope, build_heartbeat, build_state_update

__all__ = ["MessageEnvelope", "build_heartbeat", "build_state_update"]
