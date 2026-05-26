"""
LiftSim V2 — Dynamic Entities (Person & Enhanced Lift Support)
================================================================
State-machine-driven Person with schedule, navigation, and family/furniture logic.
PersonState tracks lifecycle: home → lobby → lift → outside → (reverse).
Enhanced lifts integrate via passenger management and hall-call coordination.
"""

from __future__ import annotations

import math
import random
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from building import Building, Flat, Floor
    from lift_system import Lift

from clock import WorldClock


# ── Constants ────────────────────────────────────────────────────────────

# Time a person takes to walk into/out of a lift (real seconds)
ENTER_EXIT_TIME_NORMAL = 0.6
ENTER_EXIT_TIME_FURNITURE = ENTER_EXIT_TIME_NORMAL * 3.0  # 1.8s

FURNITURE_CAPACITY_COST = 3  # furniture occupant counts as 3 slots


# ══════════════════════════════════════════════════════════════════════════
# PersonState Enum
# ══════════════════════════════════════════════════════════════════════════

class PersonState(Enum):
    AT_HOME = auto()
    WALKING_TO_LOBBY = auto()
    WAITING_FOR_LIFT = auto()
    APPROACHING_LIFT = auto()
    ENTERING_LIFT = auto()
    IN_LIFT = auto()
    EXITING_LIFT = auto()
    OUTSIDE_BUILDING = auto()


# ── Person Type ──────────────────────────────────────────────────────────

class PersonType(Enum):
    WORKER = "worker"          # Leaves morning, returns evening
    STUDENT = "student"        # Leaves morning, returns afternoon
    ELDER = "elder"            # Flexible, shorter outings
    CHILD = "child"            # Follows parent (leader)
    PET = "pet"                # Follows owner (leader)
    SHOPPER = "shopper"        # Mid-day errands


# ══════════════════════════════════════════════════════════════════════════
# PersonSchedule — Generates daily activity schedules
# ══════════════════════════════════════════════════════════════════════════

class PersonSchedule:
    """Generates and stores daily schedule events for a Person.

    Events are lists of (sim_minute, activity) pairs where:
      - activity = "leave" → person exits building
      - activity = "home" → person returns to flat
    """

    ACTIVITY_LEAVE = "leave"
    ACTIVITY_HOME = "home"

    # ── Base schedules per type ──────────────────────────────────────────
    # hour → activity (weekday)
    BASE_WEEKDAY: Dict[PersonType, List[Tuple[int, str]]] = {
        PersonType.WORKER:   [(7, "leave"),  (18, "home")],
        PersonType.STUDENT:  [(7, "leave"),  (15, "home")],
        PersonType.ELDER:    [(9, "leave"),  (11, "home"),
                              (14, "leave"), (16, "home")],
        PersonType.CHILD:    [(-1, "follow")],   # follows leader
        PersonType.PET:      [(-1, "follow")],    # follows leader
        PersonType.SHOPPER:  [(10, "leave"), (13, "home")],
    }

    # Weekend: simpler, shifted later
    BASE_WEEKEND: Dict[PersonType, List[Tuple[int, str]]] = {
        PersonType.WORKER:   [(10, "leave"), (15, "home")],
        PersonType.STUDENT:  [(10, "leave"), (18, "home")],
        PersonType.ELDER:    [(9, "leave"),  (11, "home")],
        PersonType.CHILD:    [(-1, "follow")],
        PersonType.PET:      [(-1, "follow")],
        PersonType.SHOPPER:  [(11, "leave"), (14, "home")],
    }

    def __init__(self, person_type: PersonType,
                 offset_max: int = 30) -> None:
        self.person_type: PersonType = person_type
        self.offset_max: int = offset_max
        # Events are stored as (sim_minutes_of_day, activity)
        self.weekday_events: List[Tuple[int, str]] = []
        self.weekend_events: List[Tuple[int, str]] = []
        self._generate()

    def _generate(self) -> None:
        """Generate events with random offset applied per event."""
        for base, target in [
            (self.BASE_WEEKDAY[self.person_type], self.weekday_events),
            (self.BASE_WEEKEND[self.person_type], self.weekend_events),
        ]:
            for hour, activity in base:
                if activity == "follow":
                    target.append((-1, "follow"))
                else:
                    offset = random.randint(-self.offset_max, self.offset_max)
                    mins = hour * 60 + offset
                    mins = max(0, min(1439, mins))
                    target.append((mins, activity))

    def get_current_activity(self, clock: WorldClock,
                             is_follower: bool = False) -> Optional[str]:
        """Check schedule to see what the person should be doing now.

        Returns None if no action needed (stay in current state).
        """
        if is_follower:
            return None  # Followers check their leader, not schedule

        events = self.weekend_events if clock.is_weekend else self.weekday_events
        now = clock.get_total_minutes()

        for mins, activity in events:
            if abs(now - mins) <= 2:  # Within 2-minute window
                return activity

        return None

    def next_event_time(self, clock: WorldClock) -> Optional[int]:
        """Get the next event's sim-minute (for debugging)."""
        events = self.weekend_events if clock.is_weekend else self.weekday_events
        now = clock.get_total_minutes()
        for mins, activity in events:
            if mins >= now:
                return mins
        return None


# ══════════════════════════════════════════════════════════════════════════
# Person
# ══════════════════════════════════════════════════════════════════════════

class Person:
    """A single resident with a state machine, schedule, and movement.

    Visible as a small coloured dot on the building cross-section.
    """

    # Visual colours per type
    TYPE_COLORS: Dict[PersonType, Tuple[int, int, int]] = {
        PersonType.WORKER:   (80,  180, 255),
        PersonType.STUDENT:  (100, 230, 140),
        PersonType.ELDER:    (200, 180, 120),
        PersonType.CHILD:    (255, 160, 180),
        PersonType.PET:      (200, 140, 255),
        PersonType.SHOPPER:  (255, 200, 80),
    }

    STATE_LABELS: Dict[PersonState, str] = {
        PersonState.AT_HOME:          "🏠",
        PersonState.WALKING_TO_LOBBY: "🚶",
        PersonState.WAITING_FOR_LIFT: "⏳",
        PersonState.APPROACHING_LIFT: "🚶",
        PersonState.ENTERING_LIFT:    "➡️",
        PersonState.IN_LIFT:          "🛗",
        PersonState.EXITING_LIFT:     "⬅️",
        PersonState.OUTSIDE_BUILDING: "🌳",
    }

    def __init__(self, person_id: str, person_type: PersonType,
                 home_flat: Any, building: Any,
                 config: Any, carrying_furniture: bool = False) -> None:
        self.person_id: str = person_id
        self.person_type: PersonType = person_type
        self.home_flat = home_flat
        self.home_floor: int = home_flat.floor
        self.building = building
        self.config = config
        self.carrying_furniture: bool = carrying_furniture

        # ── State Machine ───────────────────────────────────────────────
        self.state: PersonState = PersonState.AT_HOME

        # ── Schedule ────────────────────────────────────────────────────
        self.schedule: PersonSchedule = PersonSchedule(
            person_type,
            offset_max=config.SCHEDULE_OFFSET_MAX,
        )

        # ── Leader/Follower (Family Logic) ──────────────────────────────
        self.leader: Optional[Person] = None
        self.followers: List[Person] = []

        # ── Navigation ──────────────────────────────────────────────────
        self.px: float = 0.0   # screen x
        self.py: float = 0.0   # screen y
        self.target_x: float = 0.0
        self.target_y: float = 0.0
        self._target_reached: bool = True
        self._waypoints: List[Tuple[float, float]] = []

        # ── Movement state ──────────────────────────────────────────────
        self._hall_call_made: bool = False  # prevent spamming hall calls

        # ── Lift interaction ────────────────────────────────────────────
        self._enter_exit_timer: float = 0.0
        self._assigned_lift: Optional[Any] = None
        self.target_floor: int = 0  # floor we want the lift to take us to
        self._waiting_floor: int = -1  # floor snapshot when entering WAITING_FOR_LIFT

        # ── Sprite animation ─────────────────────────────────────────────
        self._anim_timer: float = 0.0
        self._last_dt: float = 0.0

        # ── Debug ───────────────────────────────────────────────────────
        self._last_think_minute: int = -1

        # Set initial position
        self._start_at_home()

    @property
    def current_floor(self) -> int:
        """Calculate which floor the person is currently on from y-position.

        Person stands on the floor surface (= top_line + FLOOR_HEIGHT).
        Formula: NUM_FLOORS - int(rel_y / FLOOR_HEIGHT).
        """
        cfg = self.config
        rel_y = self.py - cfg.BUILDING_Y
        if rel_y < 0:
            return cfg.NUM_FLOORS - 1
        floor = cfg.NUM_FLOORS - int(rel_y // cfg.FLOOR_HEIGHT)
        return max(0, min(cfg.NUM_FLOORS - 1, floor))

    # ── Geometry Helpers ─────────────────────────────────────────────────

    def _flat_door_pos(self) -> Tuple[float, float]:
        """Get the position at the flat door, feet ON the floor surface.

        Floor surface = separator line below this flat's floor.
        Person's feet sit exactly on this line.
        """
        cfg = self.config
        floor_y = cfg.BUILDING_Y + (cfg.NUM_FLOORS - 1 - self.home_floor) * cfg.FLOOR_HEIGHT
        floor_surface = floor_y + cfg.FLOOR_HEIGHT  # The separator line below
        flr = self.home_flat
        flats = self.building.floors[self.home_floor].flats
        flat_index = flats.index(flr)
        rect = flr.get_rect(flat_index, len(flats))
        return (float(rect.centerx), float(floor_surface))

    def _lobby_lift_pos(self) -> Tuple[float, float]:
        """Get position at ground floor near the centered lift shaft."""
        cfg = self.config
        ground_y = cfg.BUILDING_Y + (cfg.NUM_FLOORS - 1) * cfg.FLOOR_HEIGHT
        floor_surface = ground_y + cfg.FLOOR_HEIGHT  # Lobby floor surface
        lobby_x = cfg.LIFT_SHAFT_X + cfg.LIFT_SHAFT_WIDTH // 2
        return (float(lobby_x), float(floor_surface))

    def _outside_pos(self) -> Tuple[float, float]:
        """Get position just outside the building."""
        cfg = self.config
        ground_y = cfg.BUILDING_Y + (cfg.NUM_FLOORS - 1) * cfg.FLOOR_HEIGHT
        floor_surface = ground_y + cfg.FLOOR_HEIGHT
        return (float(cfg.BUILDING_X + cfg.BUILDING_WIDTH + 25),
                float(floor_surface))

    def _lift_door_pos(self, lift: Any) -> Tuple[float, float]:
        """Get position at the lift door — lift floor (bottom of car).

        The lift floor aligns with the building floor surface when stopped.
        """
        return (float(lift._cached_x + lift.config.LIFT_WIDTH // 2),
                float(lift.current_y + lift.config.LIFT_HEIGHT))

    # ── Position Initialisation ──────────────────────────────────────────

    def _start_at_home(self) -> None:
        """Set initial position at the flat door."""
        self.px, self.py = self._flat_door_pos()
        self._target_reached = True

    # ── Think: Decision Making (called every sim-minute) ────────────────

    def think(self, clock: WorldClock) -> None:
        """Evaluate schedule and make decisions. Called ~once per sim-minute.

        Args:
            clock: The simulation WorldClock.
        """
        # Skip if already mid-trip or following a leader
        if self.state != PersonState.AT_HOME and self.state != PersonState.OUTSIDE_BUILDING:
            return

        # Prevent duplicate think() within same sim-minute
        current_min = clock.get_total_minutes()
        if current_min == self._last_think_minute:
            return
        self._last_think_minute = current_min

        # Followers: sync to leader
        if self.leader is not None:
            self._sync_follower_to_leader()
            return

        # Check schedule
        activity = self.schedule.get_current_activity(clock)
        if activity is None:
            return

        if activity == "leave" and self.state == PersonState.AT_HOME:
            self._start_leave()

        elif activity == "home" and self.state == PersonState.OUTSIDE_BUILDING:
            self._start_return()

    def _sync_follower_to_leader(self) -> None:
        """Followers mimic their leader's destination."""
        if self.leader is None:
            return

        if self.leader.state == PersonState.AT_HOME:
            self.state = PersonState.AT_HOME
            self._start_at_home()
        elif self.leader.state == PersonState.OUTSIDE_BUILDING:
            self.state = PersonState.OUTSIDE_BUILDING
        elif self.leader.state in (PersonState.WALKING_TO_LOBBY,
                                   PersonState.WAITING_FOR_LIFT,
                                   PersonState.ENTERING_LIFT,
                                   PersonState.IN_LIFT,
                                   PersonState.EXITING_LIFT):
            # Follow leader's phase if we're still at home
            if self.state == PersonState.AT_HOME:
                self._start_leave()
            elif self.state == PersonState.OUTSIDE_BUILDING:
                self._start_return()

    # ── Trip Logic ───────────────────────────────────────────────────────

    def _start_leave(self) -> None:
        """Begin the journey from home to outside."""
        self.state = PersonState.WALKING_TO_LOBBY
        self._hall_call_made = False
        self._assigned_lift = None
        self._waiting_floor = -1
        # Remove from flat occupant count
        if self.person_id in self.home_flat.occupants:
            self.home_flat.occupants.remove(self.person_id)

        # Waypoints: flat door → shaft on home floor (same y, just horizontal)
        px, py = self._flat_door_pos()
        self.px, self.py = px, py

        shaft_x, _ = self._lobby_lift_pos()
        self._waypoints = [
            (shaft_x, py),  # Walk sideways to shaft entrance on this floor
        ]
        self._waypoint_index = 0
        self._target_reached = False
        self.target_floor = 0  # going to ground floor

    def _start_return(self) -> None:
        """Begin the journey from outside back to flat."""
        self.state = PersonState.WALKING_TO_LOBBY
        self._hall_call_made = False
        self._assigned_lift = None
        self._waiting_floor = -1

        # Start outside
        self.px, self.py = self._outside_pos()
        lobby_x, lobby_y = self._lobby_lift_pos()

        self._waypoints = [
            (lobby_x - 40, lobby_y),   # Approach building
            (lobby_x, lobby_y),         # At lobby lift area
        ]
        self._waypoint_index = 0
        self._target_reached = False
        self.target_floor = self.home_floor  # going to home floor

    # ── Update: Movement & State Transitions ────────────────────────────

    def update(self, dt: float, building: Any, lifts: List[Any]) -> None:
        """Advance this person by dt seconds.

        Handles pixel movement toward waypoints, state transitions
        for lift boarding/alighting, and hall-call signalling.
        """
        cfg = self.config

        # ── Update sprite animation timer ──────────────────────────
        if self.state in (PersonState.WALKING_TO_LOBBY,
                          PersonState.APPROACHING_LIFT,
                          PersonState.EXITING_LIFT):
            self._anim_timer += dt

        if self.state == PersonState.AT_HOME:
            return  # Nothing to do

        if self.state == PersonState.OUTSIDE_BUILDING:
            return  # Not on screen

        if self.state == PersonState.IN_LIFT:
            # We're riding — check if our assigned lift has reached our floor
            if self._assigned_lift is not None:
                lift = self._assigned_lift
                if (lift.current_floor == self.target_floor and
                        lift.state.name in ("DOORS_OPEN", "WAITING")):
                    self._begin_exit()
            return

        if self.state == PersonState.APPROACHING_LIFT:
            if not self._target_reached and self._waypoints:
                tx, ty = self._waypoints[0]
                dx = tx - self.px
                dy = ty - self.py
                dist = math.hypot(dx, dy)
                walk_speed = cfg.WALK_SPEED * dt
                if self.carrying_furniture:
                    walk_speed *= 0.5
                if dist <= walk_speed:
                    self.px, self.py = tx, ty
                    self._target_reached = True
                    # At lift door — start boarding
                    if self._assigned_lift:
                        self._begin_enter(self._assigned_lift)
                else:
                    self.px += (dx / dist) * walk_speed
                    self.py += (dy / dist) * walk_speed
            return

        if self.state == PersonState.ENTERING_LIFT:
            self._enter_exit_timer -= dt
            if self._enter_exit_timer <= 0.0:
                self.state = PersonState.IN_LIFT
                # Notify the lift that we've boarded (for queue management)
                if self._assigned_lift is not None:
                    try:
                        self._assigned_lift.notify_boarded(self.person_id)
                    except AttributeError:
                        pass
            return

        if self.state == PersonState.EXITING_LIFT:
            self._enter_exit_timer -= dt
            if self._enter_exit_timer <= 0.0:
                self._finish_exit()
            return

        # ── Movement phase ──────────────────────────────────────────────
        # Walk toward current waypoint
        if not self._target_reached and self._waypoints:
            tx, ty = self._waypoints[self._waypoint_index]
            dx = tx - self.px
            dy = ty - self.py
            dist = math.hypot(dx, dy)

            walk_speed = cfg.WALK_SPEED * dt
            if self.carrying_furniture:
                walk_speed *= 0.5  # slower with furniture

            if dist <= walk_speed:
                # Reached waypoint
                self.px, self.py = tx, ty
                self._waypoint_index += 1

                if self._waypoint_index >= len(self._waypoints):
                    # All waypoints done
                    self._target_reached = True
                    self._on_path_complete(building, lifts)
                else:
                    # Set target to next waypoint
                    pass  # next frame will handle it
            else:
                # Move toward waypoint
                self.px += (dx / dist) * walk_speed
                self.py += (dy / dist) * walk_speed

        elif self._target_reached and self.state == PersonState.WAITING_FOR_LIFT:
            # Standing still, waiting — check if a lift has arrived
            self._check_lift_arrival(lifts)
            # Also keep making hall calls if needed
            if not self._hall_call_made:
                self._make_hall_call(building, lifts)

        elif self._target_reached and self.state == PersonState.WALKING_TO_LOBBY:
            # Arrived — check if at outside (exiting building) or lobby
            ox, oy = self._outside_pos()
            if abs(self.py - oy) < 5:
                self.state = PersonState.OUTSIDE_BUILDING
            else:
                # Arrived at lobby area — start waiting for lift
                self.state = PersonState.WAITING_FOR_LIFT
                self._waiting_floor = self.current_floor  # snapshot before pixel drift
                self._make_hall_call(building, lifts)

        # ── Separation: avoid overlapping with other visible people ─────
        self._apply_separation(building)

    def _on_path_complete(self, building: Any, lifts: List[Any]) -> None:
        """Called when the person reaches the end of their waypoints."""
        if self.state == PersonState.WALKING_TO_LOBBY:
            # Check if we walked to the outside position (exiting building)
            ox, oy = self._outside_pos()
            if abs(self.py - oy) < 5:
                self.state = PersonState.OUTSIDE_BUILDING
            else:
                # We've reached the lobby area → wait for lift
                self.state = PersonState.WAITING_FOR_LIFT
                self._waiting_floor = self.current_floor  # snapshot before pixel drift
                self._make_hall_call(building, lifts)

    # ── Lift Signalling ───────────────────────────────────────────────────

    def _make_hall_call(self, building: Any, lifts: List[Any]) -> None:
        """Press the up/down button for the lift from current floor."""
        if self._hall_call_made:
            return
        # Use snapshot floor to avoid pixel-boundary drift
        floor = self._waiting_floor if self._waiting_floor >= 0 else self.current_floor
        direction = "up" if self.target_floor > floor else "down"
        building.lift_system.handle_hall_call(floor, direction)
        self._hall_call_made = True

    def _check_lift_arrival(self, lifts: List[Any]) -> None:
        """Check if any lift is at our floor — queue for boarding if so.

        People automatically queue sorted by distance to the lift door.
        The lift calls them one-by-one to approach and board.
        """
        # Use snapshot floor to avoid pixel-boundary drift
        check_floor = self._waiting_floor if self._waiting_floor >= 0 else self.current_floor
        for lift in lifts:
            if (lift.current_floor == check_floor
                    and lift.state.name in ("DOORS_OPEN", "WAITING")
                    and not lift.is_full()):
                # Queue for boarding if not already in queue
                door_x = lift._cached_x + lift.config.LIFT_WIDTH // 2
                dist = abs(self.px - door_x)
                lift.queue_for_boarding(self.person_id, dist)

                # If it's my turn, start approaching the lift door
                if (lift._current_boarder == self.person_id
                        and self.state == PersonState.WAITING_FOR_LIFT):
                    self._start_approaching_lift(lift)
                    return

    def _start_approaching_lift(self, lift: Any) -> None:
        """Walk toward the lift door (lift floor level) to board."""
        self.state = PersonState.APPROACHING_LIFT
        self._waiting_floor = -1  # no longer waiting
        self._assigned_lift = lift
        door_x = lift._cached_x + lift.config.LIFT_WIDTH // 2
        door_y = lift.current_y + lift.config.LIFT_HEIGHT  # Lift floor = bottom of car
        self._waypoints = [(float(door_x), float(door_y))]
        self._waypoint_index = 0
        self._target_reached = False

    def _begin_enter(self, lift: Any) -> None:
        """Start entering the lift."""
        self.state = PersonState.ENTERING_LIFT
        self._assigned_lift = lift
        self._enter_exit_timer = (
            ENTER_EXIT_TIME_FURNITURE if self.carrying_furniture
            else ENTER_EXIT_TIME_NORMAL
        )
        # Register with lift and tell it where we want to go
        capacity_cost = FURNITURE_CAPACITY_COST if self.carrying_furniture else 1
        lift.add_passenger(self.person_id, capacity_cost)
        lift.add_car_request(self.target_floor)

    def _begin_exit(self) -> None:
        """Start exiting the lift."""
        self.state = PersonState.EXITING_LIFT
        self._enter_exit_timer = (
            ENTER_EXIT_TIME_FURNITURE if self.carrying_furniture
            else ENTER_EXIT_TIME_NORMAL
        )
        # Set position to lift door
        self.px, self.py = self._lift_door_pos(self._assigned_lift)
        # Determine where to go after exiting
        if self.target_floor == 0:
            # Going to ground → outside
            lobby_x, lobby_y = self._lobby_lift_pos()
            self._waypoints = [(lobby_x, lobby_y)]
        else:
            # Going to home floor → flat
            dx, dy = self._flat_door_pos()
            self._waypoints = [(dx, dy)]
        self._waypoint_index = 0
        self._target_reached = False

    def _finish_exit(self) -> None:
        """Complete exit — person is out of lift."""
        if self._assigned_lift:
            self._assigned_lift.remove_passenger(self.person_id)

        if self.target_floor == 0:
            # At ground → head outside
            self.state = PersonState.WALKING_TO_LOBBY
            # Redirect waypoints to outside
            ox, oy = self._outside_pos()
            self._waypoints = [(ox, oy)]
            self._waypoint_index = 0
            self._target_reached = False
        else:
            # At home floor → walk to flat
            self.state = PersonState.AT_HOME
            # Add back to flat occupant count
            if self.person_id not in self.home_flat.occupants:
                self.home_flat.occupants.append(self.person_id)
            self.px, self.py = self._flat_door_pos()
            self._target_reached = True

    # ── Separation: Crowd Avoidance ───────────────────────────────────────

    MIN_SEPARATION: float = 12.0  # px — minimum distance between people

    def _apply_separation(self, building: Any) -> None:
        """Push apart from nearby visible people to avoid overlapping.

        Uses gentle repulsion force proportional to overlap distance.
        Only checks people on the same floor (similar y-position).
        """
        my_floor_y = self.py

        for other in building.population:
            # Skip self and hidden people
            if other is self:
                continue
            if other.state in (PersonState.AT_HOME, PersonState.IN_LIFT,
                               PersonState.OUTSIDE_BUILDING,
                               PersonState.ENTERING_LIFT, PersonState.EXITING_LIFT):
                continue

            # Only separate with people on same floor (close y)
            if abs(other.py - my_floor_y) > self.config.FLOOR_HEIGHT * 0.6:
                continue

            dx = self.px - other.px
            dy = self.py - other.py
            dist = math.hypot(dx, dy)

            if 0 < dist < self.MIN_SEPARATION:
                # Push force: stronger when closer, max 0.5px per frame
                push = (self.MIN_SEPARATION - dist) / self.MIN_SEPARATION * 0.5
                if dist > 0.01:
                    self.px += (dx / dist) * push
                    self.py += (dy / dist) * push

    # ── Drawing ─────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, font: pygame.font.Font,
             camera: Any = None) -> None:
        """Draw the person as a sprite or coloured circle with state label.

        Uses pixel-art sprites when available for the character type.
        Falls back to coloured circles for types without sprites.

        Args:
            screen: Pygame surface.
            font: Font for labels.
            camera: Camera for viewport Y offset (None = no offset).
        """
        if self.state in (PersonState.AT_HOME, PersonState.IN_LIFT,
                          PersonState.OUTSIDE_BUILDING):
            return  # Hidden from view (in flat, in lift, or outside)

        # Camera Y offset
        cam_y = camera.y if camera else 0.0
        screen_y = int(self.py - cam_y)
        x = int(self.px)

        if x < 0 or screen_y < 0:
            return

        # Try sprite rendering
        from rendering.sprites import SpriteManager
        sm = SpriteManager.get_instance()
        sprite = None

        if sm.has_sprites(self.person_type):
            # Determine facing direction from movement
            direction = self._get_sprite_direction()

            # Pick standing or walk frame
            if self.state in (PersonState.WALKING_TO_LOBBY,
                              PersonState.APPROACHING_LIFT):
                from rendering.sprites import WALK_CYCLE_DURATION as WCD, WALK_FRAMES as WF
                walk_frame = int(self._anim_timer / WCD * WF) % WF
                sprite = sm.get_walk(self.person_type, direction, walk_frame)
            else:
                sprite = sm.get_standing(self.person_type, direction)

        if sprite:
            # Scale sprite to display size and draw centered on position
            ds = self.config.SPRITE_DISPLAY_SIZE
            if sprite.get_width() != ds:
                sprite = pygame.transform.smoothscale(sprite, (ds, ds))
            sw, sh = ds, ds
            screen.blit(sprite, (x - sw // 2, screen_y - sh))  # Feet at floor

            # Furniture indicator overlay
            if self.carrying_furniture:
                pygame.draw.rect(screen, (200, 150, 80),
                                 (x - 4, screen_y - sh // 2 - 5, 8, 6),
                                 border_radius=1)

            # Leader indicator (small yellow dot above sprite)
            if self.leader is not None:
                pygame.draw.circle(screen, (255, 220, 80),
                                   (x, screen_y - sh // 2 - 5), 2)
        else:
            # Fallback: coloured circle
            colour = self.TYPE_COLORS.get(self.person_type, (200, 200, 200))
            radius = 6 if not self.carrying_furniture else 8

            pygame.draw.circle(screen, colour, (x, screen_y), radius)
            pygame.draw.circle(screen, (30, 30, 40), (x, screen_y), radius, width=1)

            # Furniture indicator
            if self.carrying_furniture:
                pygame.draw.rect(screen, (200, 150, 80),
                                 (x - 4, screen_y - 9, 8, 6), border_radius=1)

            # Leader indicator
            if self.leader is not None:
                pygame.draw.circle(screen, (255, 220, 80),
                                   (x, screen_y - radius - 3), 2)

        # State label above person
        label = self.STATE_LABELS.get(self.state, "")
        if label and font:
            surf = font.render(label, True, (200, 200, 220))
            screen.blit(surf, (x - surf.get_width() // 2,
                               screen_y - 28))

    def _get_sprite_direction(self) -> str:
        """Determine facing direction from current movement."""
        from rendering.sprites import SpriteManager
        sm = SpriteManager.get_instance()

        if not self._target_reached and self._waypoints:
            wx, wy = self._waypoints[0]
            dx = wx - self.px
            dy = wy - self.py
            import math
            dist = math.hypot(dx, dy)
            if dist > 0.01:
                facing = sm.get_facing_direction(dx / dist, dy / dist)
                self._last_facing = facing
                return facing

        # Idle or no target — keep previous facing
        return getattr(self, '_last_facing', 'south')

    def __repr__(self) -> str:
        return (f"<Person {self.person_id} ({self.person_type.value}) "
                f"{self.state.name}>")


# ══════════════════════════════════════════════════════════════════════════
# Population Generator
# ══════════════════════════════════════════════════════════════════════════

def generate_population(building: Any, config: Any,
                        density: float = 0.7) -> List[Person]:
    """Generate Person instances for all flats in the building.

    Args:
        building: The Building instance.
        config: SimulationConfig.
        density: Fraction of max capacity to fill (0.0–1.0).

    Returns:
        List of Person instances.
    """
    people: List[Person] = []
    person_counter = 0

    # Type pool for random assignment (weighted)
    type_pool = (
        [PersonType.WORKER] * 50 +
        [PersonType.STUDENT] * 20 +
        [PersonType.ELDER] * 10 +
        [PersonType.CHILD] * 12 +
        [PersonType.PET] * 8 +
        [PersonType.SHOPPER] * 15
    )
    random.shuffle(type_pool)

    for floor in building.floors:
        if floor.level == 0:
            continue  # lobby, no residents

        for flat in floor.flats:
            count = int(flat.max_capacity * density)
            count = max(flat.min_capacity, min(count, flat.max_capacity))

            for _ in range(count):
                if person_counter >= len(type_pool):
                    person_counter = 0
                    random.shuffle(type_pool)

                ptype = type_pool[person_counter % len(type_pool)]
                person_counter += 1

                person_id = f"P{floor.level}{flat.flat_id[-1]}{person_counter}"

                carrying = random.random() < 0.05  # 5% chance carrying furniture

                person = Person(
                    person_id=person_id,
                    person_type=ptype,
                    home_flat=flat,
                    building=building,
                    config=config,
                    carrying_furniture=carrying,
                )
                people.append(person)
                flat.occupants.append(person_id)

    # ── Assign leader/follower relationships ─────────────────────────
    # Children and pets follow a random adult in the same flat
    for person in people:
        if person.person_type in (PersonType.CHILD, PersonType.PET):
            # Find an adult in the same flat
            flat_adults = [
                p for p in people
                if p.home_flat is person.home_flat
                and p.person_type in (PersonType.WORKER, PersonType.SHOPPER, PersonType.ELDER)
                and p is not person
            ]
            if flat_adults:
                leader = random.choice(flat_adults)
                person.leader = leader
                leader.followers.append(person)

    return people
