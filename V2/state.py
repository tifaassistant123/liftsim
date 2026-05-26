"""
LiftSim V2 — GameState
=======================
Simple state machine for the simulation lifecycle.
"""

from enum import Enum, auto


class GameState(Enum):
    MENU = auto()
    GENERATING = auto()
    SIMULATING = auto()
