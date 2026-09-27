# SWARM-X PRO V2 Project Audit

## Executive Summary

This repository already contains a substantial backend and a dashboard prototype for a warehouse robotics fleet coordination system. The strongest implemented area is the simulation-aware backend logic built around a realistic warehouse graph, CBAA-style task allocation, reservation-based path planning, and a dashboard that consumes backend status data.

However, the project does not yet satisfy the requested end-state architecture described in the brief. The current implementation is best described as a backend-driven simulation prototype with a real warehouse model, not a fully decentralized edge-agent fleet system.

The key architectural issue is that the runtime logic is still centrally orchestrated by the FastAPI service and shared global state rather than by independent robot edge agents communicating peer-to-peer over ZeroMQ.

## Current Architecture

### 1. Backend

Primary backend entry point:
- backend/api/main.py

Framework:
- FastAPI
- Pydantic models for state and API contracts
- WebSocket support for live event broadcasts

Core runtime modules:
- backend/core/state.py: global in-memory state manager
- backend/models/schemas.py: robot/task/node data models
- backend/simulation/engine.py: simulation loop
- backend/allocation/cbaa.py: centralized task allocation logic
- backend/planning/astar.py: A* path planner with time-space reservations
- backend/coordination/reservation.py: vertex/edge reservation manager
- backend/coordination/deadlock.py: deadlock dependency graph and recovery
- backend/data/warehouse_real.py: authoritative warehouse geometry and graph
- backend/evaluation/metrics.py: metrics tracker

### 2. Visualization / Dashboard

Primary dashboard entry point:
- visualization/src/App.tsx

Framework:
- React + Vite + TypeScript
- Recharts for charts
- xlsx for spreadsheet export
- REST API consumption to FastAPI backend
- WebSocket connection for event log updates

### 3. Webots Simulation Folder

Contents indicate a simulation platform scaffold but not the final CoppeliaSim iteration described in the brief:
- webots_simulation/config/
- webots_simulation/controllers/
- webots_simulation/protos/
- webots_simulation/tools/
- webots_simulation/worlds/

This appears to be a partial, platform-specific simulation scaffold rather than a complete end-to-end automation layer. It is not the central runtime for the current backend.

### 4. Backups

The backup directories are references to prior project states and should stay read-only:
- backend_backup_before_warehouse/
- backend_backup_integration/

These offer historical code references, but they are not the active runtime path.

## Existing Components

### Real Warehouse Model

Implemented and largely functional:
- backend/data/warehouse_real.py

This module defines:
- warehouse bounds
- shelf locations and blocked zones
- columns and obstacles
- loading docks
- unloading docks
- charging stations
- robot spawn positions
- collision-avoidance validation functions
- node graph generation

The graph is authored to match the warehouse geometry and is used during global state initialization.

### Real Warehouse Initialization

Implemented:
- POST /api/warehouse/real/init

This populates the in-memory warehouse graph and robot states. It is one of the strongest working flows in the codebase.

### Robot and Task Models

Implemented:
- models/schemas.py

This includes:
- Node
- Robot
- Task
- AllocationResponse
- TrajectoryStep
- PlanningResponse

### CBAA Allocation

Implemented:
- backend/allocation/cbaa.py

This computes a bid using the authoritative 4 normalized parameters: distance (0.40), travel_time (0.30), congestion (0.20), and availability (0.10). Energy and workload are completely absent from the bid formula. It also exposes a risk model integration path.

### Path Planning

Implemented:
- backend/planning/astar.py

This includes:
- unconstrained A*
- time-space A*
- reservation checks
- conflict detection
- replan tracking

### Reservation and Deadlock Logic

Implemented:
- backend/coordination/reservation.py
- backend/coordination/deadlock.py

These provide:
- vertex reservation tracking
- edge reservation tracking
- deadlock dependency graph
- recovery attempts

### Simulation Loop

Implemented:
- backend/simulation/engine.py

This advances robot positions along their trajectory, updates battery/health, handles charging, emits WebSocket events, and processes obstacles/failure events.

### FastAPI Dashboard Endpoints

Implemented:
- /api/health
- /api/config
- /api/warehouse
- /api/robots
- /api/tasks
- /api/allocations
- /api/bids
- /api/paths
- /api/reservations
- /api/conflicts
- /api/events
- /api/failures
- /api/benchmark
- /api/peer/status
- /api/peer/messages
- /api/state
- /api/allocation/run
- /api/planning/run
- /api/simulation/start
- /api/simulation/stop
- /api/simulation/reset
- /api/health/nodes
- /api/congestion
- /api/obstacles
- /api/deadlocks
- /api/metrics
- /api/ai/status
- /api/ai/metrics
- /api/ai/features
- /api/ai/train
- /api/ai/predict

### Dashboard UI

Implemented:
- visualization/src/App.tsx
- visualization/src/services/api.ts
- visualization/src/components/CbaaBidTransparency.tsx

The dashboard has multiple tabs, KPI cards, task forms, charts, and event-driven refreshes.

## Working Functionality

The following behaviors are present and appear to function based on code structure and test coverage:

1. Real warehouse initialization
   - backend/data/warehouse_real.py
   - tests/test_real_warehouse.py

2. Warehouse node generation and graph connectivity
   - generate_real_warehouse_graph()
   - connectivity check from R1 spawn is expected to cover all nodes

3. Base FastAPI app boots and exposes health/config endpoints
   - /api/health
   - /api/config
   - /api/gazebo/status

4. CBAA allocation for a simple task can return a winner
   - allocator.allocate_task(task_id)

5. A* style planning can produce a path and trajectory
   - planner.plan_time_space_astar(...)

6. Simulation run loop processes robot trajectory progression and emits events
   - simulator.run()

7. Dynamic obstacle and failure hooks are wired into backend endpoints
   - /api/obstacles
   - /api/failures

8. Dashboard UI can fetch backend data and render live event updates
   - visualization/src/App.tsx uses fetch and WebSocket connections

## Broken or Incomplete Functionality

The following are either absent or not implemented as specified by the brief:

1. Distributed edge-agent architecture
   - No actual peer-to-peer ZeroMQ robot agents exist.
   - No per-robot independent state or planner process.
   - FastAPI remains the central coordinator for allocation and planning decisions.

2. CoppeliaSim integration
   - The project is not integrating CoppeliaSim Edu 4.10 as required.
   - The simulation is an in-memory backend engine, not a real simulator like CoppeliaSim.

3. Real decoupled robot coordination
   - R1/R2/R3/R4 do not own independent decision processes.
   - no edge_agents/ package
   - no multi-agent communication topology

4. True ZeroMQ peer-to-peer communication layer
   - No ZeroMQ runtime is implemented.
   - No message envelopes, no heartbeat protocol, no stale detection, no duplicate rejection.

5. Full warehouse configuration model
   - There is no central YAML/JSON warehouse configuration matching the required parameterization.
   - Real warehouse constants are embedded in Python code rather than in a configurable central schema.

6. Dynamic obstacle and failure handling are simplified
   - The project includes hooks, but not the full deterministic traffic arbitration and dynamic replanning pipeline demanded by the brief.

7. The dashboard includes “Judge Mode” and “proof/demo” language
   - The UI uses terms explicitly prohibited by the brief (e.g., “Judge Mode”).
   - This violates the user-facing terminology rules.

8. Actual CBAA distributed consensus is missing
   - Winner selection is centralized inside allocator.allocate_task().
   - No independent bid exchange between robots is implemented.

9. Unclear separation of concerns
   - The backend mixes simulation, allocation, planning, telemetry, and dashboard API responsibilities into one service.

10. Validation gaps
   - The codebase contains many features but the actual architecture does not match the required distributed fleet model.

## Reusable Code

The following code is worth preserving and building upon:

- backend/data/warehouse_real.py
- backend/models/schemas.py
- backend/allocation/cbaa.py
- backend/planning/astar.py
- backend/coordination/reservation.py
- backend/coordination/deadlock.py
- backend/simulation/engine.py
- backend/api/main.py
- visualization/src/App.tsx
- visualization/src/services/api.ts

These components provide a strong foundation for a realistic warehouse model and a backend dashboard contract. The project already has a useful set of state objects and a consistent simulation vocabulary.

## Deprecated or High-Risk Code

These areas appear to be legacy or not aligned with the final target architecture:

- The current API and logic are very central-state oriented.
- The dashboard includes the “Judge Mode” flow and other demo-oriented naming.
- Several modules appear to have been previously adapted for a hackathon review and were not refactored for a production/distributed simulation architecture.
- Real-time logic is built around a single global state object rather than an edge-agent ownership model.

## Missing Functionality

The following are still absent relative to the target project brief:

- edge_agents/ package and robot-local autonomous logic
- ZeroMQ peer-to-peer communication layer
- CoppeliaSim scene/config/model layout
- scenario generation suite with 10 required scenarios
- structured data generation pipeline under data/
- ML dataset specification document and preprocessing scripts
- industrial dashboard redesign without prohibited labeling
- comprehensive test suite for the full distributed architecture
- deployment and operations documentation
- clean separation between monitoring APIs and robot decision-making

## Recommended Migration Path

1. Preserve the real warehouse graph and the current FastAPI service as the monitoring and task-injection layer.
2. Separate the robot decision layer from FastAPI:
   - build per-robot edge agents
   - implement local planner and local task allocator
   - implement direct peer-to-peer ZeroMQ messaging
3. Refactor CBAA so that each robot computes and broadcasts its own bid instead of using central allocator.allocate_task().
4. Keep the current A* planner as a prototype, but move it behind the edge-agent architecture with clear local planning responsibilities.
5. Retain the current dashboard as an operational monitor, but remove demo-oriented language and align it with a professional fleet operations UI.
6. Add a proper simulation config package and scenario runner on top of the existing warehouse model.
7. Validate with incremental tests as each phase moves from prototype to distributed simulation architecture.

## Implementation Sequence Based on Actual Codebase

Based on the actual code, the sensible sequence is:

1. Keep warehouse_real.py, state models, and API patterns intact.
2. Establish the new architecture boundary: FastAPI becomes monitoring/task API, not fleet decision maker.
3. Add a per-robot edge-agent abstraction that owns state, task bidding, local route planning, and obstacle handling.
4. Implement a lightweight ZeroMQ communication layer with deterministic envelopes and heartbeat logic.
5. Replace central allocation logic with distributed CBAA and winner claim propagation.
6. Expand from one robot path to four robots under independent local planning.
7. Add traffic arbitration and deadlock handling.
8. Add failure detection and task reopening.
9. Feed telemetry into dashboard and metrics generation.
10. Add dataset generation, benchmarking, and final documentation.

## Final Assessment

The project is not starting from zero, and it already contains a credible warehouse model plus useful early simulation backend code. That said, the project does not yet match the desired architecture: it is still a centralized backend simulation with a dashboard, not a decentralized edge-agent fleet simulation.

The most important next step is not to rewrite everything. The correct path is to keep the working warehouse graph, state models, and API contract, then separate planetary decision-making from FastAPI and move coordination to the robot edge layer.
