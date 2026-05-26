"""
LiftSim V2 — SimSettings
=========================
User-facing settings dataclass. All UI controls write to this.
The engine reads from it when rebuilding the simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class SimSettings:
    """All configurable settings exposed in the menu UI."""

    # ── Building ────────────────────────────────────────────────────────
    num_floors: int = 10
    """4–14 floors."""

    flats_per_floor: int = 3
    """1–6 flats per residential floor."""

    mode: str = "pixel"
    """'pixel' mode uses fixed FLOOR_HEIGHT (54px) for sprite integration."""

    # ── Lifts ───────────────────────────────────────────────────────────
    num_lifts: int = 2
    """1–4 lifts."""

    lift_speed: float = 2.0
    """0.5–4.0 floors per second."""

    lift_capacity: int = 10
    """4–20 passenger slots."""

    door_dwell: float = 3.0
    """1–10 seconds doors stay open."""

    # ── Population ──────────────────────────────────────────────────────
    population_density: float = 0.7
    """0.1–1.0 fraction of flat capacity filled."""

    # ── Visual ──────────────────────────────────────────────────────────
    theme: str = "modern"
    show_fps: bool = False

    # ── Misc ────────────────────────────────────────────────────────────
    start_hour: int = 7
    """Simulation start hour (0–23)."""

    start_speed: int = 1


def calc_floor_height(num_floors: int, screen_h: int, top_margin: int = 60, bottom_margin: int = 60) -> int:
    """Return fixed pixel-scaled floor height for sprite integration.

    With 72px sprites + 36px headroom = 108px per floor.
    Building scrolls if taller than screen — no more dynamic fitting.
    """
    return 108


def calc_building_width(screen_w: int) -> int:
    """Calculate a good building width that leaves room for UI panels."""
    return min(500, screen_w - 320)
