from __future__ import annotations

import multiprocessing as mp
import time

from edge_agents.communication.manager import RobotCommunicationManager


def _start_robot(robot_id: str):
    mgr = RobotCommunicationManager(
        robot_id=robot_id,
        pub_endpoint={
            'R1': 'tcp://127.0.0.1:55501',
            'R2': 'tcp://127.0.0.1:55502',
            'R3': 'tcp://127.0.0.1:55503',
            'R4': 'tcp://127.0.0.1:55504',
        }[robot_id],
        sub_endpoints=[
            'tcp://127.0.0.1:55501',
            'tcp://127.0.0.1:55502',
            'tcp://127.0.0.1:55503',
            'tcp://127.0.0.1:55504',
        ],
    )
    try:
        mgr.start()
        for _ in range(12):
            mgr.publish_message('HEARTBEAT', {'battery': 85.0})
            time.sleep(0.1)
            mgr.receive_messages(50)
    finally:
        mgr.close()


def test_four_process_zero_mq_heartbeat_exchange():
    ctx = mp.get_context('spawn')
    processes = [ctx.Process(target=_start_robot, args=(rid,)) for rid in ['R1', 'R2', 'R3', 'R4']]

    try:
        for proc in processes:
            proc.start()
        for proc in processes:
            proc.join(timeout=20)
            assert not proc.is_alive(), f"robot {proc.name} still alive after shutdown"
    finally:
        for proc in processes:
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=5)

    assert len(processes) == 4
