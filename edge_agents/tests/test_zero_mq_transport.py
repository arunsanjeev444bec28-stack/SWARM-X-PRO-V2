from __future__ import annotations

import json
import threading
import time

import pytest

from edge_agents.communication.manager import RobotCommunicationManager
from edge_agents.communication.protocol import MessageEnvelope


@pytest.fixture
def manager():
    mgr = RobotCommunicationManager(
        robot_id="R1",
        pub_endpoint="tcp://127.0.0.1:55501",
        sub_endpoints=["tcp://127.0.0.1:55502", "tcp://127.0.0.1:55503", "tcp://127.0.0.1:55504"],
        heartbeat_hz=5.0,
        stale_timeout_seconds=0.6,
        dead_timeout_seconds=2.0,
    )
    yield mgr
    mgr.close()


def test_envelope_validation_accepts_valid_message():
    mgr = RobotCommunicationManager("R1")
    envelope = {
        "msg_type": "HEARTBEAT",
        "sender_id": "R2",
        "seq": 10,
        "timestamp": 123.0,
        "payload": {"battery": 90.0},
    }
    validated = mgr.validate_envelope(envelope)
    assert validated.msg_type == "HEARTBEAT"
    assert validated.sender_id == "R2"


def test_envelope_validation_rejects_invalid_type():
    mgr = RobotCommunicationManager("R1")
    with pytest.raises(ValueError):
        mgr.validate_envelope({"msg_type": "BAD_TYPE", "sender_id": "R2", "seq": 1, "timestamp": 1.0, "payload": {}})


def test_sequence_tracker_rejects_duplicate_and_old_sequence():
    tracker = mgr = RobotCommunicationManager("R1")
    assert tracker.sequence_tracker.accept("R2", 1)
    assert tracker.sequence_tracker.accept("R2", 2)
    assert not tracker.sequence_tracker.accept("R2", 2)
    assert not tracker.sequence_tracker.accept("R2", 1)


def test_heartbeat_message_and_state_tracking():
    mgr = RobotCommunicationManager("R1")
    envelope = MessageEnvelope("HEARTBEAT", "R2", 7, time.time(), {"battery": 80.0})
    mgr._update_neighbor_from_message(envelope)
    status = mgr.neighbor_status["R2"]
    assert status.connection_state == "ONLINE"
    assert status.last_sequence == 7


def test_stale_and_dead_timeout_assessment():
    mgr = RobotCommunicationManager("R1")
    now = time.time()
    mgr.neighbor_status["R2"] = type('X', (), {"robot_id": "R2", "last_seen": now - 1.0, "last_sequence": 3, "connection_state": "ONLINE"})()
    state = mgr.assess_neighbor_state(now)
    assert state["R2"] == "STALE"

    mgr.neighbor_status["R3"] = type('Y', (), {"robot_id": "R3", "last_seen": now - 3.0, "last_sequence": 5, "connection_state": "ONLINE"})()
    state = mgr.assess_neighbor_state(now)
    assert state["R3"] == "DEAD"


def test_real_tcp_pub_sub_roundtrip():
    context = __import__('zmq').Context()
    r1 = context.socket(__import__('zmq').PUB)
    r1.bind('tcp://127.0.0.1:55511')
    r2 = context.socket(__import__('zmq').SUB)
    r2.setsockopt(__import__('zmq').SUBSCRIBE, b'')
    r2.connect('tcp://127.0.0.1:55511')

    try:
        time.sleep(0.2)
        envelope = MessageEnvelope('HEARTBEAT', 'R1', 20, time.time(), {'battery': 92.0})
        r1.send_multipart([b'R1', json.dumps(envelope.to_dict()).encode('utf-8')])

        poller = __import__('zmq').Poller()
        poller.register(r2, __import__('zmq').POLLIN)
        ready = dict(poller.poll(2000))
        assert r2 in ready, "subscriber did not receive the heartbeat within timeout"

        recv = r2.recv_multipart()
        assert recv[0] == b'R1'
        assert b'HEARTBEAT' in recv[1]
    finally:
        r1.close(); r2.close(); context.term()
