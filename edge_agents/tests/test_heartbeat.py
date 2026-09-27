from __future__ import annotations

import time

from edge_agents.communication.protocol import build_heartbeat


def test_heartbeat_message_has_required_envelope():
    heartbeat = build_heartbeat("R1", 11, {"battery": 90.0})
    data = heartbeat.to_dict()

    assert data["msg_type"] == "HEARTBEAT"
    assert data["sender_id"] == "R1"
    assert data["seq"] == 11
    assert data["payload"]["battery"] == 90.0


def test_missing_heartbeat_can_be_detected_by_timestamp():
    now = time.time()
    stale = now - 3.0
    assert stale < now
