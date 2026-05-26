"""
LiftSim V2 — SimulationConfig
================================
Single source of truth for all simulation constants.
Uses @dataclass for clean, type-hinted configuration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class SimulationConfig:
    """Immutable-style configuration container for LiftSim."""

    # ── Sprite / Character ─────────────────────────────────────────────
    SPRITE_SIZE: int = 36
    """Pixel Lab sprite size in pixels."""

    SPRITE_HEADROOM: int = 36
    """Extra px above sprite for ceiling clearance."""

    SPRITE_DISPLAY_SIZE: int = 72
    """Display size after scaling (SPRITE_SIZE * scale)."""

    SPRITE_WALK_FRAMES: int = 6
    """Number of walk animation frames per direction."""

    SPRITE_WALK_DURATION: float = 0.8
    """Seconds per complete walk cycle."""

    SPRITE_DIRECTIONS: List[str] = field(
        default_factory=lambda: ["west", "north-west", "north", "north-east",
                                 "east", "south-east", "south", "south-west"]
    )

    # ── Building ────────────────────────────────────────────────────────
    FLOOR_HEIGHT: int = 108
    """Height of each floor in pixels (SPRITE_SIZE + SPRITE_HEADROOM)."""

    NUM_FLOORS: int = 10
    """Total number of floors (ground + residential)."""

    FLATS_PER_FLOOR: int = 3
    """Number of flats on each residential floor (1–6)."""

    NUM_LIFTS: int = 2
    """Number of lift shafts (1–4)."""

    # ── Flat Layout ─────────────────────────────────────────────────────
    FLAT_WIDTH: int = 70
    """Width of each flat unit in pixels."""

    GAP_WIDTH: int = 12
    """Corridor/landing gap between flats and lift shaft, per side."""

    # Layout positions (filled dynamically by engine at rebuild time)
    LIFT_SHAFT_X: int = 0
    """Screen x-coordinate of the left edge of the lift shaft area."""

    LIFT_SHAFT_WIDTH: int = 0
    """Width of the entire lift shaft area."""

    LEFT_FLATS_X: int = 0
    """Screen x-coordinate where left-side flats start."""

    LEFT_FLATS_WIDTH: int = 0
    """Width of the left flats area."""

    RIGHT_FLATS_X: int = 0
    """Screen x-coordinate where right-side flats start."""

    RIGHT_FLATS_WIDTH: int = 0
    """Width of the right flats area."""

    # ── Movement ────────────────────────────────────────────────────────
    WALK_SPEED: float = 50.0
    """Person walk speed in pixels per second."""

    LIFT_SPEED: float = 2.0
    """Lift speed in floors per second (at 1x scale)."""

    LIFT_DOOR_DWELL: float = 3.0
    """Seconds the lift doors stay open at a floor."""

    # ── S-Curve Movement Physics ─────────────────────────────────────────
    ACCEL_MAX: float = 80.0
    """Maximum lift acceleration in px/s^2 for S-curve profiles."""

    JERK_LIMIT: float = 400.0
    """Maximum jerk in px/s^3. Controls motion smoothness."""

    CREEP_SPEED: float = 12.0
    """Final approach/leveling speed in px/s (~10% of max speed)."""

    LEVELING_THRESHOLD: float = 8.0
    """Distance in px to enter creep mode during floor approach."""

    ARRIVAL_THRESHOLD: float = 0.5
    """Distance in px for final sub-pixel alignment snap."""

    LIFT_MAX_PX_SPEED: float = 0.0
    """Max speed in px/s (computed as LIFT_SPEED * FLOOR_HEIGHT). Filled in __post_init__."""

    # ── Time ────────────────────────────────────────────────────────────
    TIME_SCALE: int = 1
    """Starting time multiplier (1x, 2x, or 4x)."""

    SPEED_MULTIPLIERS: Dict[int, int] = field(
        default_factory=lambda: {1: 1, 2: 2, 3: 4}
    )
    """Maps key index (1/2/3) to simulated speed multiplier."""

    SIM_SECONDS_PER_REAL_SECOND: int = 60
    """At 1x speed, 1 real second = 60 sim-seconds (1 sim-minute)."""

    # ── Screen ──────────────────────────────────────────────────────────
    SCREEN_WIDTH: int = 1024
    SCREEN_HEIGHT: int = 1024
    FPS: int = 60

    # ── Flat Size Capacities ────────────────────────────────────────────
    FLAT_CAPACITIES: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: {
            "studio": (1, 2),
            "1br":    (1, 3),
            "2br":    (2, 5),
            "3br":    (3, 7),
        }
    )
    """Flat type → (min_residents, max_residents)."""

    TOP_FLOOR_IS_STUDIO: bool = True
    """Top floor flats are always studio-sized."""

    # ── Schedule ────────────────────────────────────────────────────────
    SCHEDULE_OFFSET_MAX: int = 30
    """Max random minutes a person's schedule can shift."""

    WEEKEND_OFFSET_MAX: int = 120
    """Max random minutes for weekend schedule shifts."""

    # ── Building Rendering ────────────────────────────────────────────
    BUILDING_X: int = 40
    """Left edge of the building on screen."""

    BUILDING_Y: int = 80
    """Top edge of the building on screen."""

    BUILDING_WIDTH: int = 420
    """Total building width on screen."""

    BUILDING_WALL_THICKNESS: int = 8
    """Thickness of the building walls."""

    LIFT_WIDTH: int = 50
    """Width of each lift car."""

    LIFT_HEIGHT: int = 108
    """Height of each lift car (matches FLOOR_HEIGHT)."""

    LOBBY_HEIGHT: int = 128
    """Height of ground-floor lobby (extra tall +10 for entrance)."""

    LIFT_CAPACITY: int = 10
    """People-slot capacity of a lift (furniture = 3 slots)."""

    FLOOR_LINE_HEIGHT: int = 3
    """Thickness of floor separator lines."""

    # ── Flat Rendering ──────────────────────────────────────────────
    FLAT_COLORS: Dict[str, Tuple[int, int, int]] = field(
        default_factory=lambda: {
            "studio": (180, 160, 140),
            "1br":    (170, 180, 150),
            "2br":    (160, 170, 190),
            "3br":    (190, 160, 170),
        }
    )
    """Flat type → fill colour for rendering."""

    LIFT_COLORS: Dict[str, Tuple[int, int, int]] = field(
        default_factory=lambda: {
            "idle":       (140, 140, 160),
            "moving":     (100, 180, 255),
            "doors_open": (200, 220, 100),
        }
    )
    """Lift state → colour mapping."""

    # ── Sky ─────────────────────────────────────────────────────────
    SKY_COLORS: Dict[str, Tuple[int, int, int]] = field(
        default_factory=lambda: {
            "day":   (135, 206, 235),
            "night": (20,  20,  60),
            "dawn":  (255, 180, 100),
            "dusk":  (255, 120, 80),
        }
    )
    """Sky color palette mapped to time-of-day states."""
