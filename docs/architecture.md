# SWARM-X PRO V2 Target Architecture

## Purpose

This document defines the target architecture for the validated, distributed warehouse fleet implementation. It is intentionally aligned with the project brief and with the actual reusable code currently present in the repository.

## Architectural Principle

FastAPI remains a monitoring and control API layer. It is not the fleet coordinator. Decision-making and local conflict resolution live at the edge, on each robot agent.

The final system is organized around the following flow:

Simulation -> Robot Edge Agents -> ZeroMQ Peer-to-Peer Coordination -> Telemetry -> FastAPI -> Dashboard

## High-Level Components

### 1. Simulation Platform

The simulation layer represents a warehouse and provides robot state updates, dynamic obstacle injection, task generation, and scenario execution.

Target implementation:
- CoppeliaSim Edu 4.10 remote API integration
- warehouse scene and navigation graph aligned to the same geometry used in backend planning
- robot state stream representing AMR motion, heading, battery, and task state

### 2. Edge Agents

Each robot owns a local process with:
- local state
- local task allocation logic
- local path planner
- local map
- local neighbor state
- collision avoidance logic
- deadlock detection
- failure handling
- replanning

This means:
- R1 can continue operating even when R2 fails
- no centralized task winner is selected by FastAPI
- the system remains operational if the FastAPI service stops

### 3. Communication Layer

Robot-to-robot communication uses ZeroMQ over localhost TCP for simulation.

Required message set:
- HEARTBEAT
- STATE_UPDATE
- TASK_ANNOUNCE
- BID
- WINNER_CLAIM
- INTENT
- OBSTACLE_REPORT
- TASK_LEASE_RENEW
- TASK_REOPEN

The communication layer includes:
- message envelope
- sequence numbers
- duplicate suppression
- stale detection
- dead detection
- heartbeat timeout
- structured logs

### 4. FastAPI Backend

FastAPI remains the operational monitor and control interface:
- inject tasks
- expose telemetry
- serve dashboard APIs
- start/stop/reset scenarios
- expose metrics and event streams
- provide simulation configuration read endpoints

FastAPI must not:
- select CBAA winners centrally
- calculate fleet-wide path plans
- resolve robot conflicts centrally
- act as a required communication broker

### 5. Dashboard

The dashboard consumes live state from the backend and displays:
- warehouse overview
- robot fleet status
- task queue
- conflict information
- event timeline
- operational KPIs
- telemetry and metrics

The UI must avoid demo-only terminology and remain in professional industrial operations style.

## Boundary Between Existing and New Code

The current project already provides valuable reusable pieces:
- warehouse geometry and graph in [backend/data/warehouse_real.py](../backend/data/warehouse_real.py)
- data model contract in [backend/models/schemas.py](../backend/models/schemas.py)
- global state wrapper in [backend/core/state.py](../backend/core/state.py)
- planning and reservation logic in [backend/planning/astar.py](../backend/planning/astar.py) and [backend/coordination/reservation.py](../backend/coordination/reservation.py)

These should be retained, but the coordination responsibility must move away from the global service into the robot edge layer.

## Phase-by-Phase Boundary Plan

### Phase 1: Architecture boundary
- document the responsibility split
- keep FastAPI as API/monitoring layer only
- add per-robot domain boundary

### Phase 2: Simulation and warehouse config
- introduce central warehouse configuration
- align geometry and navigation graph
- define scenario parameters and robot profiles

### Phase 3: Robot agent local state and messaging
- define robot-local state schema
- establish ZeroMQ peer communication
- add heartbeat and state exchange

### Phase 4: Distributed CBAA
- each robot independently computes bids
- single deterministic winner selected via shared rules
- winner broadcasts claim

### Phase 5: Local planner and traffic control
- A* remains as local planner foundation
- add intersection arbitration and deterministic waiting logic

### Phase 6: Recovery, failure, and datasets
- failed robot detection and task reopening
- telemetry logging and dataset generation
- metrics and benchmarking

## Implementation Constraints

- Do not centralize winner selection in FastAPI.
- Do not fabricate CoppeliaSim or ZeroMQ integration that is not present.
- Keep the existing warehouse model and API contracts where they still align with the final architecture.
- Add clear separation between implemented and planned features.
- Preserve all code that already works while gradually refactoring the architecture.
