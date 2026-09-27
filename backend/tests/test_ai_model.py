import pytest
import os
import json
from intelligence.risk_model import train_model
from intelligence.inference import predict_risk, load_model

def test_model_training():
    # Model should already be trained by the user script, but let's check its existence
    assert os.path.exists("data/risk_model.joblib")
    assert os.path.exists("data/ai_metrics.json")
    
    with open("data/ai_metrics.json", "r") as f:
        metrics = json.load(f)
        
    assert "accuracy" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1" in metrics
    assert "roc_auc" in metrics
    assert metrics["trained"] is True
    
def test_inference_module():
    # Load model
    model = load_model()
    assert model is not None
    
    # Test valid features
    features = {
        "battery": 50.0,
        "temperature": 30.0,
        "load": 0.5,
        "robot_health": 100.0,
        "task_priority": 2.0,
        "task_urgency": 1.0,
        "distance_to_pickup": 5.0,
        "distance_to_dispatch": 10.0,
        "estimated_energy": 20.0,
        "current_workload": 0.0,
        "path_length": 15.0,
        "congestion_probability": 0.1,
        "reservation_conflict_count": 0.0,
        "nearby_robot_count": 1.0,
        "node_health": 100.0,
        "dynamic_obstacle_present": 0.0,
        "deadline": 100.0,
        "remaining_deadline": 100.0,
        "replan_count": 0.0
    }
    
    res = predict_risk(features)
    assert "risk_probability" in res
    assert "risk_class" in res
    assert 0.0 <= res["risk_probability"] <= 1.0
    assert res["risk_class"] in [0, 1]
    assert "error" not in res
