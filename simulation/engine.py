"""
Backward compatibility bridge for simulation.engine.
Re-exports the legacy discrete step simulator from backend.simulation.engine.
"""

from backend.simulation.engine import simulator, SimulatorEngine

__all__ = ["simulator", "SimulatorEngine"]
