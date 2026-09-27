import pytest
import os
import csv
from intelligence.dataset import generate_episode
from core.state import global_state

@pytest.mark.asyncio
async def test_generate_episode():
    records = await generate_episode(42, 1, num_robots=2, num_tasks=2)
    
    assert len(records) > 0
    
    first_rec = records[0]
    assert "scenario_id" in first_rec
    assert "run_id" in first_rec
    assert "robot_id" in first_rec
    assert "task_id" in first_rec
    assert "features" in first_rec
    assert "label" in first_rec
    assert "risk_reason" in first_rec
    
    features = first_rec["features"]
    assert "battery" in features
    assert "temperature" in features
    assert "distance_to_pickup" in features
    
    # Ensure risk label is 0 or 1
    assert first_rec["label"] in [0, 1]
