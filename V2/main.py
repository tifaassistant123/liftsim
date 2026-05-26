"""
LiftSim V2 — Entry Point
=========================
Launches the professional OOP lift simulator.
"""

import sys
import os

# Ensure the package root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SimulationConfig
from engine import SimulationEngine


def main() -> None:
    """Create config and launch the simulation."""
    config = SimulationConfig(
        FLOOR_HEIGHT=54,
        NUM_FLOORS=22,
        NUM_LIFTS=2,
        SCREEN_WIDTH=1024,
        SCREEN_HEIGHT=1024,
    )
    SimulationEngine.launch(config)


if __name__ == "__main__":
    main()
