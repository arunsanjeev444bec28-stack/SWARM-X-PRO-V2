# SWARM-X PRO V2

## Overview

This project contains an existing warehouse simulation backend and dashboard that have already been built for earlier project review cycles. The current objective is not to replace these modules, but to add the missing edge-agent boundary while preserving the existing CBAA, A*, warehouse, API, and dashboard functionality.

## Project status

The repository currently contains a reusable backend and dashboard implementation, plus new additive edge-agent modules under the top-level `edge_agents/` folder.

## Edge-agent boundary

The new edge-agent layer is intentionally additive and non-invasive:

- `edge_agents/common` contains the robot state and adapter definitions.
- `edge_agents/communication` contains the message envelope and peer topology abstraction.
- `edge_agents/robot_agent` contains the robot-local edge-agent class and entry point.
- `edge_agents/coordination` contains local CBAA logic for distributed bidding.
- `edge_agents/planning` contains a local planning interface.
- `edge_agents/tests` contains the Phase 1 boundary tests.

## Existing functionality preserved

The current backend and dashboard remain in place and are not rewritten or removed in this phase.

## Launching four independent agents

Run four processes separately:

```
python -m edge_agents.robot_agent.main --robot-id R1
python -m edge_agents.robot_agent.main --robot-id R2
python -m edge_agents.robot_agent.main --robot-id R3
python -m edge_agents.robot_agent.main --robot-id R4
```

These process boundaries represent the initial milestone requirement for independent robot agents.

## ZeroMQ topology

The current mesh topology for the edge-agent layer is:

- R1 <-> R2
- R1 <-> R3
- R1 <-> R4
- R2 <-> R3
- R2 <-> R4
- R3 <-> R4

This is represented in the code as a peer topology abstraction in `edge_agents/communication/mesh.py`.

## Important note

This is Phase 1 only. It introduces the edge-agent boundary and local decision models without breaking the pre-existing backend or dashboard. It does not yet replace the current central allocation or planning logic.
