import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.main import app
from core.state import global_state
from coordination.reservation import reservation_manager
from evaluation.metrics import metrics_tracker
from simulation.engine import simulator

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    global_state.reset()
    reservation_manager.reset()
    metrics_tracker.completed_tasks = 0
    metrics_tracker.failed_tasks = 0
    metrics_tracker.allocation_success = 0
    metrics_tracker.total_distance = 0.0
    metrics_tracker.replan_count = 0
    metrics_tracker.collision_count = 0
    metrics_tracker.alternate_path_count = 0
    metrics_tracker.wait_fallback = 0
    metrics_tracker.reservation_conflicts = 0
    metrics_tracker.task_completion_times = []
    metrics_tracker.pickup_events = 0
    metrics_tracker.dispatch_events = 0
    simulator.is_running = False
    simulator.current_time_step = 0

def test_api_full_lifecycle():
    # 1. Health check
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    
    # 2. Add Warehouse Node
    node_payload = {
        "node_id": "N_0_0",
        "x": 0.0,
        "y": 0.0,
        "type": "NORMAL",
        "neighbors": ["N_0_1"]
    }
    response = client.post("/api/warehouse", json=node_payload)
    assert response.status_code == 200
    assert response.json()["node_id"] == "N_0_0"
    
    node_payload2 = {
        "node_id": "N_0_1",
        "x": 0.0,
        "y": 1.0,
        "type": "NORMAL",
        "neighbors": ["N_0_0", "N_0_2"]
    }
    client.post("/api/warehouse", json=node_payload2)
    
    node_payload3 = {
        "node_id": "N_0_2",
        "x": 0.0,
        "y": 2.0,
        "type": "NORMAL",
        "neighbors": ["N_0_1"]
    }
    client.post("/api/warehouse", json=node_payload3)
    
    # 3. Add Robot
    robot_payload = {
        "robot_id": "R1",
        "node_id": "N_0_0",
        "battery": 100.0,
        "temperature": 25.0,
        "load": 0.0,
        "health": 100.0,
        "status": "IDLE"
    }
    response = client.post("/api/robots", json=robot_payload)
    assert response.status_code == 200
    assert response.json()["robot_id"] == "R1"
    
    # 4. Add Task
    task_payload = {
        "task_id": "T1",
        "pickup_node": "N_0_1",
        "dispatch_node": "N_0_2",
        "priority": "HIGH",
        "urgency": 1.0,
        "deadline": 60.0,
        "load": 1.0,
        "energy_requirement": 5.0
    }
    response = client.post("/api/tasks", json=task_payload)
    assert response.status_code == 200
    assert response.json()["task_id"] == "T1"
    
    # 5. Run Allocation
    response = client.post("/api/allocation/run?task_id=T1")
    assert response.status_code == 200
    alloc_res = response.json()
    assert alloc_res["winner"] == "R1"
    assert "R1" in alloc_res["bids"]
    assert "feasible_robots" in alloc_res
    
    # 6. Run Planning
    response = client.post("/api/planning/run?robot_id=R1&task_id=T1&start_time=0")
    assert response.status_code == 200
    plan_res = response.json()
    assert plan_res["robot_id"] == "R1"
    assert "path" in plan_res
    assert len(plan_res["path"]) > 0
    assert "trajectory" in plan_res
    
    # 7. Start Simulation
    response = client.post("/api/simulation/start")
    assert response.status_code == 200
    assert response.json()["status"] == "Simulation started"
    
    # Let the simulation run synchronously since we just started it as an async task in fastapi
    # Wait, the TestClient uses a synchronous loop, but `simulator.run()` is scheduled. 
    # Because FastAPI TestClient doesn't automatically run asyncio tasks spawned in the background,
    # we might just want to check that the metrics endpoint returns correctly format metrics.
    
    # 8. Get Metrics
    response = client.get("/api/metrics")
    assert response.status_code == 200
    metrics = response.json()
    assert "completed_tasks" in metrics
    assert "allocation_success" in metrics
    assert metrics["allocation_success"] == 1
