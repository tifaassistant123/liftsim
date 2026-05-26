"""
LiftSim V2 — Professional OOP Lift Simulator
==============================================
"""

import sys
import os

_sys_path = os.path.dirname(os.path.abspath(__file__))
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from config import SimulationConfig  # noqa: E402
from clock import WorldClock         # noqa: E402
from engine import SimulationEngine  # noqa: E402
from building import Building        # noqa: E402
from lift_system import LiftSystem, Lift, LiftState  # noqa: E402
from state import GameState          # noqa: E402
from settings import SimSettings, calc_floor_height  # noqa: E402
from ui.theme import Theme           # noqa: E402

__all__ = [
    "SimulationConfig", "WorldClock", "SimulationEngine",
    "Building", "LiftSystem", "Lift", "LiftState",
    "GameState", "SimSettings", "calc_floor_height",
    "Theme",
]
__version__ = "2.1.0"
