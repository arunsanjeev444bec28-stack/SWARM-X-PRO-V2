import time
import json
import numpy as np
from intelligence.inference import predict_risk, load_model

def run_benchmark(num_predictions=1000):
    print(f"Starting Edge-AI inference benchmark ({num_predictions} samples)...")
    
    model = load_model()
    if not model:
        print("Error: Model not trained. Please train the model first.")
        return
        
    # Generate dummy features for benchmarking
    # We use random but plausible values to ensure realistic branching
    dummy_features = []
    for _ in range(num_predictions):
        features = {
            "battery": np.random.uniform(10, 100),
            "temperature": np.random.uniform(20, 50),
            "load": np.random.uniform(0, 1),
            "robot_health": np.random.uniform(0, 100),
            "task_priority": np.random.choice([1.0, 2.0, 3.0, 4.0]),
            "task_urgency": np.random.uniform(0.5, 2.0),
            "distance_to_pickup": np.random.uniform(1, 20),
            "distance_to_dispatch": np.random.uniform(1, 20),
            "estimated_energy": np.random.uniform(5, 50),
            "current_workload": np.random.choice([0.0, 1.0]),
            "path_length": np.random.uniform(2, 40),
            "congestion_probability": np.random.uniform(0, 1),
            "reservation_conflict_count": np.random.uniform(0, 5),
            "nearby_robot_count": np.random.uniform(0, 10),
            "node_health": np.random.uniform(50, 100),
            "dynamic_obstacle_present": np.random.choice([0.0, 1.0]),
            "deadline": np.random.uniform(50, 200),
            "remaining_deadline": np.random.uniform(10, 200),
            "replan_count": np.random.uniform(0, 3)
        }
        dummy_features.append(features)
        
    latencies = []
    
    # Warmup
    for _ in range(10):
        predict_risk(dummy_features[0])
        
    total_start = time.time()
    
    for feats in dummy_features:
        t0 = time.time()
        predict_risk(feats)
        t1 = time.time()
        latencies.append((t1 - t0) * 1000.0) # convert to ms
        
    total_end = time.time()
    
    total_elapsed = (total_end - total_start) * 1000.0
    mean_ms = np.mean(latencies)
    median_ms = np.median(latencies)
    p95_ms = np.percentile(latencies, 95)
    
    print("\nBenchmark Results:")
    print("-" * 30)
    print(f"Total Predictions: {num_predictions}")
    print(f"Total Elapsed Time: {total_elapsed:.2f} ms")
    print(f"Mean Inference: {mean_ms:.3f} ms")
    print(f"Median Inference: {median_ms:.3f} ms")
    print(f"p95 Inference: {p95_ms:.3f} ms")
    
    # Verify we aren't faking the edge performance
    if mean_ms > 50:
        print("\nWARNING: Inference is slow (>50ms per prediction). Edge execution may bottleneck the allocator.")
    else:
        print("\nSUCCESS: Inference is fast and suitable for edge execution during CBAA.")
        
    report = {
        "total_predictions": num_predictions,
        "total_elapsed_ms": float(total_elapsed),
        "mean_inference_ms": float(mean_ms),
        "median_inference_ms": float(median_ms),
        "p95_inference_ms": float(p95_ms)
    }
    
    with open("data/ai_benchmark.json", "w") as f:
        json.dump(report, f, indent=2)

if __name__ == "__main__":
    run_benchmark(1000)
