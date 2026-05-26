"""
LiftSim V2 — Enhanced Lift & LiftSystem with S-Curve Physics
=============================================================
Professional fleet management for the building's lifts.

Lift:     A single lift car with S-curve physics, state machine,
          floor-leveling, and passenger management.
LiftSystem: The "Brain" that owns and coordinates all lifts.

States: IDLE -> ACCELERATING -> CRUISING -> DECELERATING
        -> LEVELING -> ARRIVED -> OPENING_DOORS -> WAITING
        -> CLOSING_DOORS -> IDLE | MOVING

Physics: Jerk-limited S-curve motion profiles for smooth movement.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pygame

from config import SimulationConfig
from physics import (
    PhaseType, ProfileSegment, MotionProfile,
    compute_s_curve_profile, compute_leveling_profile,
    s_curve_braking_distance,
)
from rendering.sprites import LiftSpriteLoader


# ── Lift State Machine ───────────────────────────────────────────────────

class LiftState(Enum):
    IDLE = "idle"
    MOVING = "moving"
    DOORS_OPEN = "doors_open"
    OPENING_DOORS = "opening_doors"
    WAITING = "waiting"
    CLOSING_DOORS = "closing_doors"


class MovementPhase(Enum):
    """Sub-states of MOVING, for S-curve tracking."""
    CALCULATING = "calculating"       # Computing profile
    ACCELERATING = "accelerating"     # T1+T2+T3
    CRUISING = "cruising"             # T4
    DECELERATING = "decelerating"     # T5+T6+T7
    LEVELING = "leveling"             # Creep toward floor
    SNAPPING = "snapping"             # Final sub-pixel alignment


# ── Lift ─────────────────────────────────────────────────────────────────

class Lift:
    """A single lift car with S-curve physics and passenger management.

    Uses jerk-limited S-curve motion profiles computed by the physics
    module. Supports floor-leveling with creep speed final approach.

    Enhanced state machine:
      IDLE -> MOVING (S-curve accel/cruise/decel) -> LEVELING
        -> OPENING_DOORS -> WAITING (boarding)
        -> CLOSING_DOORS -> IDLE | MOVING
    """

    # ── Physics Constants ───────────────────────────────────────────────
    DOOR_ANIM_TIME: float = 0.5    # seconds for open/close animation

    def __init__(self, lift_id: int, home_floor: int, config: SimulationConfig,
                 lift_system: Optional[Any] = None) -> None:
        self.lift_id: int = lift_id
        self.config: SimulationConfig = config

        # ── Position & Physics ──────────────────────────────────────
        self.current_floor: int = home_floor
        self.current_y: float = self._floor_to_y(home_floor)
        self.velocity: float = 0.0
        self.acceleration: float = 0.0

        # ── State & Direction (SCAN) ────────────────────────────────
        self.state: LiftState = LiftState.IDLE
        self.direction: int = 0  # 1=UP, -1=DOWN, 0=STOPPED
        self._target_floor: int = home_floor
        self._target_floor_valid: bool = False
        self.move_phase: Optional[MovementPhase] = None
        self.door_timer: float = 0.0
        self._anim_timer: float = 0.0

        # ── SCAN Hall Calls & Car Requests ──────────────────────────
        self.lift_system: Optional[Any] = lift_system  # parent for hall call access
        self.car_requests: set = set()  # passenger-selected destination floors

        # ── S-Curve Profile ─────────────────────────────────────────
        self._profile: Optional[MotionProfile] = None
        self._profile_time: float = 0.0
        self._profile_start_y: float = 0.0
        self._profile_target_y: float = 0.0
        self._profile_direction: float = 1.0  # +1 = down, -1 = up (screen coords)

        # ── Leveling ────────────────────────────────────────────────
        self._leveling_profile: Optional[MotionProfile] = None
        self._leveling_time: float = 0.0
        self._leveling_start_y: float = 0.0
        self._creep_speed: float = config.CREEP_SPEED if hasattr(config, 'CREEP_SPEED') else 12.0
        self._arrival_threshold: float = getattr(config, 'ARRIVAL_THRESHOLD', 0.5)

        # ── Capacity ────────────────────────────────────────────────
        self.max_capacity: int = config.LIFT_CAPACITY
        self.passenger_ids: List[str] = []
        self._used_capacity: int = 0

        # ── Sequential Boarding ─────────────────────────────────────
        self.boarding_queue: List[Tuple[str, float]] = []
        self._current_boarder: Optional[str] = None

        # ── Drawing ────────────────────────────────────────────────
        self._cached_x: int = 0
        self._debug_font: Any = None

        # ── Door Animation Sprites ────────────────────────────────
        self._lift_sprites: LiftSpriteLoader = LiftSpriteLoader.get_instance()
        self._scaled_frames: List[Optional[pygame.Surface]] = []
        self._cache_scaled_frames()

    # ── Geometry ─────────────────────────────────────────────────────────

    def _floor_to_y(self, floor: int) -> float:
        """Convert a floor number to its y-coordinate on screen.

        Floor 0 is ground (bottom of building).
        Higher floor numbers are higher on screen (lower y value).
        """
        return float(
            self.config.BUILDING_Y
            + (self.config.NUM_FLOORS - 1 - floor) * self.config.FLOOR_HEIGHT
        )

    def get_x(self, num_lifts: int, lift_index: int) -> int:
        """Calculate horizontal position for this lift in the centered shaft."""
        shaft_left = self.config.LIFT_SHAFT_X
        shaft_width = self.config.LIFT_SHAFT_WIDTH
        cell_width = shaft_width // num_lifts
        lift_x = shaft_left + lift_index * cell_width + (cell_width - self.config.LIFT_WIDTH) // 2
        return max(shaft_left, min(lift_x, shaft_left + shaft_width - self.config.LIFT_WIDTH))

    def load_factor(self) -> float:
        return self._used_capacity / max(self.max_capacity, 1)

    def is_full(self) -> bool:
        return self._used_capacity >= self.max_capacity

    # ── Passenger Management ─────────────────────────────────────────────

    def add_passenger(self, person_id: str, capacity_cost: int = 1) -> None:
        self.passenger_ids.append(person_id)
        self._used_capacity += capacity_cost
        setattr(self, f"_cost_{person_id}", capacity_cost)

    def remove_passenger(self, person_id: str) -> None:
        if person_id in self.passenger_ids:
            self.passenger_ids.remove(person_id)
            cost = getattr(self, f"_cost_{person_id}", 1)
            self._used_capacity = max(0, self._used_capacity - cost)
            try:
                delattr(self, f"_cost_{person_id}")
            except AttributeError:
                pass

    # ── Sequential Boarding ──────────────────────────────────────────────

    BOARDING_GRACE: float = 1.5

    def queue_for_boarding(self, person_id: str, dist: float) -> None:
        if person_id == self._current_boarder:
            return
        for pid, _ in self.boarding_queue:
            if pid == person_id:
                return
        self.boarding_queue.append((person_id, dist))
        self.boarding_queue.sort(key=lambda x: x[1])

    def notify_boarded(self, person_id: str) -> None:
        if self._current_boarder == person_id:
            self._current_boarder = None
            self.door_timer = self.BOARDING_GRACE

    # ── SCAN Navigation ────────────────────────────────────────────────

    def add_car_request(self, floor: int) -> None:
        """Register a passenger's destination floor (pressed inside the lift)."""
        if 0 <= floor < self.config.NUM_FLOORS:
            self.car_requests.add(floor)

    def _compute_next_target(self) -> None:
        """SCAN: find next floor using elevator algorithm.

        The lift services all requests in its current direction before
        reversing. Hall calls are matched by direction (UP calls when
        going up, DOWN calls when going down).
        """
        cfg = self.config
        floor = self.current_floor

        # Get hall calls from the LiftSystem manager
        up_calls = self.lift_system.up_hall_calls if self.lift_system else set()
        down_calls = self.lift_system.down_hall_calls if self.lift_system else set()

        # All pending requests for reverse-direction check
        all_requests = self.car_requests | up_calls | down_calls

        if not all_requests:
            self._target_floor_valid = False
            self.direction = 0
            self.state = LiftState.IDLE
            return

        if self.direction >= 0:
            # ── Going UP (or idle trying UP first) ──────────────────
            # 1) Same-direction stops first (car requests + UP hall calls)
            same_dir_ahead = {f for f in (self.car_requests | up_calls) if f > floor}
            if same_dir_ahead:
                self._target_floor = min(same_dir_ahead)
                self.direction = 1
                self._target_floor_valid = True
                return
            # 2) No same-direction ahead — check if ANY request exists above
            any_ahead = {f for f in all_requests if f > floor}
            if any_ahead:
                # Continue UP to the highest pending floor (sweep peak)
                self._target_floor = max(any_ahead)
                self.direction = 1
            else:
                # 3) Nothing above anywhere — reverse to DOWN
                below = {f for f in all_requests if f < floor}
                if below:
                    self._target_floor = max(below)
                else:
                    self._target_floor = min(all_requests)
                self.direction = -1
        else:
            # ── Going DOWN ─────────────────────────────────────────
            # 1) Same-direction stops first (car requests + DOWN hall calls)
            same_dir_ahead = {f for f in (self.car_requests | down_calls) if f < floor}
            if same_dir_ahead:
                self._target_floor = max(same_dir_ahead)
                self.direction = -1
                self._target_floor_valid = True
                return
            # 2) No same-direction ahead — check if ANY request exists below
            any_below = {f for f in all_requests if f < floor}
            if any_below:
                # Continue DOWN to the lowest pending floor (sweep bottom)
                self._target_floor = min(any_below)
                self.direction = -1
            else:
                # 3) Nothing below anywhere — reverse to UP
                above = {f for f in all_requests if f > floor}
                if above:
                    self._target_floor = min(above)
                else:
                    self._target_floor = max(all_requests)
                self.direction = 1

        self._target_floor_valid = True

    def _clear_requests_for_floor(self) -> None:
        """Remove all requests for the current floor after arrival."""
        f = self.current_floor
        self.car_requests.discard(f)
        if self.lift_system:
            self.lift_system.up_hall_calls.discard(f)
            self.lift_system.down_hall_calls.discard(f)

    # ── Old Navigation (removed) ────────────────────────────────────────
    # add_stop(), clear_stops(), get_next_stop() replaced by SCAN above ─────────────────────────────────────────

    def _build_profile(self) -> None:
        """Build an S-curve motion profile for the current target floor."""
        if not self._target_floor_valid:
            return
        target_y = self._floor_to_y(self._target_floor)
        dy = target_y - self.current_y

        self._profile_direction = 1.0 if dy > 0.0 else -1.0
        distance = abs(dy)
        self._profile_start_y = self.current_y
        self._profile_target_y = target_y

        v_max = self.config.LIFT_SPEED * self.config.FLOOR_HEIGHT
        a_max = getattr(self.config, 'ACCEL_MAX', 80.0)
        jerk = getattr(self.config, 'JERK_LIMIT', 400.0)

        self._profile = compute_s_curve_profile(distance, v_max, a_max, jerk)
        self._profile_time = 0.0
        self.move_phase = MovementPhase.ACCELERATING

    def _sample_profile(self) -> None:
        """Sample the current S-curve profile and update position/velocity."""
        if self._profile is None:
            return

        self._profile_time += self._last_dt if hasattr(self, '_last_dt') else 0.017

        displacement, vel, accel = self._profile.sample(self._profile_time)
        travel = displacement * self._profile_direction

        self.current_y = self._profile_start_y + travel
        self.velocity = vel * self._profile_direction
        self.acceleration = accel * self._profile_direction

        # Determine movement sub-phase from segment containing profile_time
        for seg in self._profile.segments:
            if seg.t_start <= self._profile_time <= seg.t_end:
                phase_map = {
                    PhaseType.ACCEL_JERK_UP: MovementPhase.ACCELERATING,
                    PhaseType.ACCEL_RAMP: MovementPhase.ACCELERATING,
                    PhaseType.ACCEL_JERK_DOWN: MovementPhase.ACCELERATING,
                    PhaseType.CRUISE: MovementPhase.CRUISING,
                    PhaseType.DECEL_JERK_DOWN: MovementPhase.DECELERATING,
                    PhaseType.DECEL_RAMP: MovementPhase.DECELERATING,
                    PhaseType.DECEL_JERK_UP: MovementPhase.DECELERATING,
                }
                self.move_phase = phase_map.get(seg.phase, MovementPhase.ACCELERATING)
                break

        # Check if profile is done (arrived at approx target)
        if self._profile.is_finished(self._profile_time) or travel >= abs(self._profile_target_y - self._profile_start_y):
            self._on_profile_complete()

    def _on_profile_complete(self) -> None:
        """Handle S-curve profile completion and enter leveling phase."""
        # Profile ends near target — snap to exact floor position
        self.move_phase = MovementPhase.LEVELING

        # Compute remaining distance for leveling
        remaining = abs(self._profile_target_y - self.current_y)

        if remaining <= self._arrival_threshold:
            # Close enough — immediate arrival
            self._on_arrival()
        else:
            # Enter creep-based leveling
            distance = abs(self._profile_target_y - self.current_y)
            self._leveling_profile = compute_leveling_profile(
                distance, self._creep_speed, self._arrival_threshold
            )
            self._leveling_time = 0.0
            self._leveling_start_y = self.current_y

    def _update_leveling(self, dt: float) -> None:
        """Update creep-based floor leveling."""
        if self._leveling_profile is None:
            self._on_arrival()
            return

        self._leveling_time += dt
        remaining_dist = abs(self._profile_target_y - self.current_y)

        if remaining_dist <= self._arrival_threshold:
            self._on_arrival()
            return

        # Move at creep speed toward target
        direction = 1.0 if (self._profile_target_y - self.current_y) > 0 else -1.0
        creep_step = self._creep_speed * dt
        step = min(creep_step, remaining_dist - self._arrival_threshold)
        self.current_y += step * direction
        self.velocity = self._creep_speed * direction
        self.acceleration = 0.0

    def _on_arrival(self) -> None:
        """Snap to exact floor position and transition to door opening.

        Clears hall calls and car requests for this floor so other
        lifts don't also try to service it.
        """
        self.current_y = self._profile_target_y
        self.current_floor = self._target_floor
        self.velocity = 0.0
        self.acceleration = 0.0
        self.move_phase = MovementPhase.SNAPPING

        # Clear all pending requests for this floor (hall call serviced)
        self._clear_requests_for_floor()

        # Mark target as used so we re-compute next stop after doors close
        self._target_floor_valid = False

        self.state = LiftState.OPENING_DOORS
        self._anim_timer = self.DOOR_ANIM_TIME
        self._profile = None
        self._leveling_profile = None

    # ── SCAN Update (called every frame) ────────────────────────────────

    _last_dt: float = 0.017

    def update(self, dt: float) -> None:
        """Advance lift state using SCAN elevator logic + S-curve physics."""
        self._last_dt = dt

        # ── Door animation phases ───────────────────────────────────────
        if self.state in (LiftState.OPENING_DOORS, LiftState.CLOSING_DOORS):
            self._anim_timer -= dt
            if self._anim_timer <= 0.0:
                if self.state == LiftState.OPENING_DOORS:
                    self.state = LiftState.WAITING
                    self.door_timer = self.config.LIFT_DOOR_DWELL
                else:  # CLOSING_DOORS
                    self.state = LiftState.IDLE
                    # Re-compute next target now that doors are fully closed
                    self._compute_next_target()
            return

        # ── WAITING: sequential boarding management ─────────────────────
        if self.state == LiftState.WAITING:
            if self._current_boarder is None and self.boarding_queue:
                # Don't let more people board if the lift is already full
                if self.is_full():
                    self.boarding_queue.clear()
                    self.state = LiftState.CLOSING_DOORS
                    self._anim_timer = self.DOOR_ANIM_TIME
                    return
                next_id = self.boarding_queue.pop(0)[0]
                self._current_boarder = next_id
                self.door_timer = max(self.door_timer, self.BOARDING_GRACE)

            self.door_timer -= dt
            if self.door_timer <= 0.0:
                self._current_boarder = None
                self.boarding_queue.clear()
                self.state = LiftState.CLOSING_DOORS
                self._anim_timer = self.DOOR_ANIM_TIME
            return

        # ── IDLE: find next target using SCAN ───────────────────────────
        if self.state == LiftState.IDLE:
            self._compute_next_target()
            if not self._target_floor_valid:
                return  # Nothing to do — stay idle
            # Fall through to start moving

        # ── Arrived at target floor? → open doors ──────────────────────
        if (self.velocity == 0.0 and self._target_floor_valid
                and self.current_floor == self._target_floor):
            self._on_arrival()
            return

        # ── MOVING: S-Curve Movement ────────────────────────────────────
        self.state = LiftState.MOVING

        # Build profile if needed (first frame or new target)
        if self._profile is None and self._target_floor_valid:
            self._build_profile()
            return

        # Sample the S-curve profile
        if self._profile is not None:
            self._sample_profile()

        # Leveling (creep to target)
        if self.move_phase == MovementPhase.LEVELING:
            self._update_leveling(dt)

    # ── Sprite Caching ─────────────────────────────────────────────────

    def _cache_scaled_frames(self) -> None:
        """Pre-scale all 8 door frames to match the lift car dimensions."""
        w = self.config.LIFT_WIDTH
        h = self.config.LIFT_HEIGHT
        for i in range(self._lift_sprites.frame_count):
            frame = self._lift_sprites.get_frame(i)
            if frame is not None:
                scaled = pygame.transform.scale(frame, (w, h))
                self._scaled_frames.append(scaled)
            else:
                self._scaled_frames.append(None)

    def _get_door_frame_index(self) -> int:
        """Determine which sprite frame (0-7) to draw based on door state.

        Frame 0 = doors fully closed
        Frame 7 = doors fully open

        Returns:
            0-based frame index (0-7).
        """
        total_frames = self._lift_sprites.frame_count
        if total_frames == 0:
            return 0
        max_idx = total_frames - 1  # 7

        if self.state == LiftState.OPENING_DOORS:
            # Timer counts down from DOOR_ANIM_TIME → 0
            # Progress: 0 → 1 (closed → open)
            progress = 1.0 - (self._anim_timer / self.DOOR_ANIM_TIME)
            progress = max(0.0, min(1.0, progress))
            return round(progress * max_idx)

        elif self.state == LiftState.CLOSING_DOORS:
            # Timer counts down from DOOR_ANIM_TIME → 0
            # Progress: 0 → 1 (open → closed) — reversed
            progress = 1.0 - (self._anim_timer / self.DOOR_ANIM_TIME)
            progress = max(0.0, min(1.0, progress))
            return max_idx - round(progress * max_idx)

        elif self.state in (LiftState.WAITING, LiftState.DOORS_OPEN):
            return max_idx  # Fully open

        else:
            return 0  # Closed (IDLE, MOVING, etc.)

    # ── Drawing ─────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, camera: Any = None) -> None:
        """Draw this lift car at its current position, with camera offset."""
        cfg = self.config
        cam_y = camera.y if camera else 0.0

        # Lift position
        x = self._cached_x
        y = int(self.current_y - cam_y)
        w = cfg.LIFT_WIDTH
        h = cfg.LIFT_HEIGHT

        # Skip if off-screen
        screen_h = screen.get_height()
        if y + h < -20 or y > screen_h + 20:
            return

        # Pick the correct sprite frame for door animation
        frame_idx = self._get_door_frame_index()
        door_sprite = self._scaled_frames[frame_idx] if frame_idx < len(self._scaled_frames) else None

        if door_sprite is not None:
            # Draw the sprite (full lift car visual with animated doors)
            screen.blit(door_sprite, (x, y))
        else:
            # Fallback: draw coloured rectangles
            if self.state == LiftState.MOVING:
                colour = cfg.LIFT_COLORS["moving"]
            elif self.state in (LiftState.DOORS_OPEN, LiftState.WAITING,
                                LiftState.OPENING_DOORS, LiftState.CLOSING_DOORS):
                colour = cfg.LIFT_COLORS["doors_open"]
            else:
                colour = cfg.LIFT_COLORS["idle"]

            pygame.draw.rect(screen, colour, (x, y, w, h), border_radius=3)
            pygame.draw.rect(screen, (40, 40, 55), (x, y, w, h), width=2, border_radius=3)

        # Floor number label (debug)
        debug_font = getattr(self, '_debug_font', None)
        if debug_font:
            floor_text = f"{self.current_floor}"
            surf = debug_font.render(floor_text, True, (255, 255, 255))
            screen.blit(surf, (x + w // 2 - surf.get_width() // 2,
                               y + h // 2 - surf.get_height() // 2))

    # ── Debug Info ──────────────────────────────────────────────────────

    def movement_info(self) -> str:
        """Return a debug string about current movement state."""
        dir_label = {1: "UP", -1: "DOWN", 0: "IDLE"}.get(self.direction, "?")
        parts = [
            f"Floor: {self.current_floor}",
            f"Dir: {dir_label}",
            f"Y: {self.current_y:.1f}",
            f"V: {self.velocity:.1f}",
            f"A: {self.acceleration:.1f}",
        ]
        if self.move_phase:
            parts.append(f"Phase: {self.move_phase.value}")
        if self._profile:
            parts.append(f"Profile t: {self._profile_time:.2f}/{self._profile.total_duration:.2f}")
        if self._target_floor_valid:
            parts.append(f"Target: F{self._target_floor}")
        parts.append(f"Car: {sorted(self.car_requests)}")
        return " | ".join(parts)


# ══════════════════════════════════════════════════════════════════════════
# LiftSystem: The Fleet Manager
# ══════════════════════════════════════════════════════════════════════════

class LiftSystem:
    """Manages all lifts in the building — the "Brain".

    Creates lifts based on SimulationConfig, dispatches hall calls,
    and coordinates fleet-wide updates.
    """

    def __init__(self, config: SimulationConfig) -> None:
        self.config: SimulationConfig = config
        self.lifts: List[Lift] = []

        # ── SCAN Hall Call Sets ─────────────────────────────────────
        self.up_hall_calls: set = set()    # Floors with UP button pressed
        self.down_hall_calls: set = set()  # Floors with DOWN button pressed

        for i in range(config.NUM_LIFTS):
            lift = Lift(lift_id=i, home_floor=0, config=config, lift_system=self)
            lift._cached_x = lift.get_x(config.NUM_LIFTS, i)
            self.lifts.append(lift)

    # ── SCAN Dispatch Logic ────────────────────────────────────────────

    def handle_hall_call(self, floor: int, direction: str) -> None:
        """Register a hall call in the shared directional queue.

        All lifts share `up_hall_calls` and `down_hall_calls` sets.
        Whichever lift gets to that floor first in the right direction
        will service it.
        """
        if direction == "up":
            self.up_hall_calls.add(floor)
        else:
            self.down_hall_calls.add(floor)

    def set_debug_font(self, font: Any) -> None:
        for lift in self.lifts:
            lift._debug_font = font

    # ── Fleet Update ────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        for lift in self.lifts:
            lift.update(dt)

    # ── Drawing ─────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, camera: Any = None) -> None:
        for lift in self.lifts:
            lift.draw(screen, camera=camera)

    # ── State Query ─────────────────────────────────────────────────────

    @property
    def total_passengers(self) -> int:
        return sum(len(l.passenger_ids) for l in self.lifts)

    @property
    def idle_count(self) -> int:
        return sum(1 for l in self.lifts if l.state == LiftState.IDLE)

    @property
    def active_calls(self) -> int:
        return len(self.up_hall_calls) + len(self.down_hall_calls) + sum(len(l.car_requests) for l in self.lifts)

    def __repr__(self) -> str:
        return (
            f"<LiftSystem {len(self.lifts)} lifts, "
            f"{self.idle_count} idle, "
            f"{self.total_passengers} pax, "
            f"{self.active_calls} calls>"
        )
