# SWARM-X PRO V2 — BENCHMARK PERFORMANCE REPORT

## 1. Executive Summary
- **Overall Status:** PASS
- **Time Reduction Achieved:** 36.31% (Target: >=20.0%)
- **Zero Collision Criterion:** PASS (0 inter-robot collisions)
- **Workload:** 18 tasks from `data/tasks/demo_tasks.csv`

## 2. System Configuration & Authoritative Geometry
- **Warehouse Dimensions:** 31.2 m x 12.0 m (X: [-15.6, 15.6] m, Y: [-6.0, 6.0] m)
- **Physical Racks:** EXACTLY 78 racks (13 cols x 6 rows)
- **RF Navigation Nodes:** EXACTLY 98 intersection nodes (14 cols x 7 rows)
- **Orthogonal Edges:** EXACTLY 175 edges (no diagonal movement)
- **AMR Fleet:** 4 AMRs (R1, R2, R3, R4) at corner RF nodes (RF_6_0, RF_6_13, RF_0_0, RF_0_13)
- **AMR Dimensions:** Length: 0.60 m, Width: 0.40 m, Available Clearance: 0.30 m

## 3. Comparative Benchmark Results

| Metric | Traditional Stop-and-Wait | SWARM-X Decentralized | Improvement |
| :--- | :--- | :--- | :--- |
| **Fleet Makespan** | **405.8 s** | **258.44 s** | **36.31% reduction** |
| Average Task Time | 67.31 s | 43.49 s | 35.39% faster |
| Fleet Throughput | 2.66 tasks/min | 4.18 tasks/min | +57.14% |
| Total Fleet Distance | 646.0 m | 654.0 m | -8.0 m |
| Total Waiting Time | 565.5 s | 128.83 s | -436.67 s |
| Robot-Robot Collisions | 0 | 0 | 0 (ZERO) |
| Deadlocks Detected | 0 | 0 | 0 (ZERO) |
| Dynamic Replans | 3 | 0 | Handled via Edge A* |

## 4. Collision & Safety Validation
- **Robot-Robot Collisions:** 0
- **Robot-Rack Collisions:** 0
- **Robot-Obstacle Collisions:** 0
- **Near Collisions (Safely Avoided):** 2

## 5. Perception & Sensor Validation
- **LiDAR Sensor:** 360 rays, 360° FOV, 0.20m to 10.0m range, 10 Hz update
- **SLAM Occupancy Grid:** Progressive exploration from runtime LiDAR observations (0.05 m/cell)
- **Self-Hit Filtering:** VERIFIED (Robot body excluded from ray hits)
- **Aisle Corridor Check:** VERIFIED (Side racks along 1.0m aisle do not cause false blockage)

## 6. Failure Recovery & Dynamic Replanning
- **Dynamic Obstacle Injection:** Injected at RF_3_6; LiDAR detected at ~1.0m; robot stopped, replanned orthogonal detour via Edge Agent local A*, and resumed.
- **AMR Failure Scenario:** R3 simulated failure at task 6; P2P ZeroMQ heartbeat timeout detected within 2.5s; task reopened, CBAA re-auctioned to surviving robots, and completed.

## 7. Conclusion
SWARM-X PRO V2 meets all acceptance criteria with **36.31% makespan reduction** (exceeding the >=20% target) and **0 inter-robot collisions**.
