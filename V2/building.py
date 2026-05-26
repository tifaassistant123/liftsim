"""
LiftSim V2 — Building, Floor, Flat
====================================
The physical world of LiftSim.

Building: Owns floors, a LiftSystem, and manages Person population.
Floor:    A single level with flats.
Flat:     A residential unit on a floor.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

import pygame

from config import SimulationConfig
from lift_system import LiftSystem

if TYPE_CHECKING:
    from camera import Camera
    from entities import Person


# ── Flat ─────────────────────────────────────────────────────────────────

class Flat:
    """A single residential unit on a floor.

    Attributes:
        flat_id: Unique identifier (e.g., "1A", "2B").
        flat_type: "studio", "1br", "2br", or "3br".
        floor: Floor number this flat belongs to.
        occupants: List of person IDs living here.
        furniture_ids: List of furniture item IDs in this flat.
    """

    def __init__(
        self,
        flat_id: str,
        flat_type: str,
        floor: int,
        config: SimulationConfig,
        side: str = "left",
    ) -> None:
        self.flat_id: str = flat_id
        self.flat_type: str = flat_type
        self.floor: int = floor
        self.config: SimulationConfig = config
        self.side: str = side

        # Capacity limits
        cap = config.FLAT_CAPACITIES.get(flat_type, (1, 2))
        self.min_capacity: int = cap[0]
        self.max_capacity: int = cap[1]

        # Runtime state
        self.occupants: List[str] = []
        self.furniture_ids: List[str] = []

    # ── Rendering Geometry ───────────────────────────────────────────────

    def get_rect(self, flat_index: int, flats_on_floor: int) -> pygame.Rect:
        """Get the screen rectangle for this flat.

        Flats are arranged left and right of the centered lift shaft.
        First half of flats (side="left") go on the left side,
        remaining (side="right") go on the right side.

        Args:
            flat_index: This flat's index within its floor (0, 1, 2...).
            flats_on_floor: Total flats on this floor.

        Returns:
            pygame.Rect for drawing.
        """
        cfg = self.config

        # Floor's y-position on screen
        floor_y = cfg.BUILDING_Y + (cfg.NUM_FLOORS - 1 - self.floor) * cfg.FLOOR_HEIGHT

        left_count = (flats_on_floor + 1) // 2
        flat_h = cfg.FLOOR_HEIGHT - cfg.FLOOR_LINE_HEIGHT
        fw = cfg.FLAT_WIDTH

        if self.side == "left":
            x = cfg.LEFT_FLATS_X + flat_index * fw
        else:
            right_idx = flat_index - left_count
            x = cfg.RIGHT_FLATS_X + right_idx * fw

        return pygame.Rect(
            x,
            int(floor_y) + cfg.FLOOR_LINE_HEIGHT,
            fw - 2,
            flat_h - 2,
        )

    def __repr__(self) -> str:
        return f"<Flat {self.flat_id} ({self.flat_type}) [{len(self.occupants)} occ]>"


# ── Floor ────────────────────────────────────────────────────────────────

class Floor:
    """A single level of the building containing flats."""

    def __init__(self, level: int, config: SimulationConfig) -> None:
        self.level: int = level
        self.config: SimulationConfig = config
        self.flats: List[Flat] = []

    def __repr__(self) -> str:
        return f"<Floor {self.level} [{len(self.flats)} flats]>"


# ── Building ─────────────────────────────────────────────────────────────

class Building:
    """The physical building — owns floors, the lift system, and people.

    Handles cross-section rendering with the correct draw order:
      1. Lift shafts (background)
      2. Lift cars (via LiftSystem)
      3. Floor overlays (floors + flats, in front of lifts)
      4. People (dots walking around)
    """

    def __init__(self, config: SimulationConfig) -> None:
        self.config: SimulationConfig = config
        self._font: Any = None
        self.floors: List[Floor] = []
        self.lift_system: LiftSystem = LiftSystem(config)
        self.population: List[Any] = []  # Person instances (lazy import)

        self._build_floors()

    # ── Person Management ────────────────────────────────────────────────

    def populate(self, density: float = 0.7) -> None:
        """Generate Person instances for all flats.

        Uses entities.generate_population.
        """
        from entities import generate_population
        self.population = generate_population(self, self.config, density)

    @property
    def people(self) -> List[Any]:
        """Shortcut to population list."""
        return self.population

    def think_all(self, clock: Any) -> None:
        """Call think() on every person.

        Should be called ~once per simulation minute.
        """
        for person in self.population:
            person.think(clock)

    # ── Construction ─────────────────────────────────────────────────────

    def _build_floors(self) -> None:
        """Generate the floor hierarchy with flats."""
        for level in range(self.config.NUM_FLOORS):
            floor = Floor(level, self.config)

            if level == 0:
                # Ground floor — lobby, no flats
                self.floors.append(floor)
                continue

            # Determine flat types for this floor
            is_top = level == self.config.NUM_FLOORS - 1
            flat_types = self._generate_flat_types(is_top)
            floor.flats = flat_types

            self.floors.append(floor)

    def _generate_flat_types(self, is_top: bool) -> List[Flat]:
        """Generate flat types for a residential floor.

        Splits flats left/right around the centered lift shaft.
        Top floor: all studios if TOP_FLOOR_IS_STUDIO is set.
        """
        flats: List[Flat] = []
        num_flats = self.config.FLATS_PER_FLOOR
        level = len(self.floors)  # current floor level

        if is_top and self.config.TOP_FLOOR_IS_STUDIO:
            types = ["studio"] * num_flats
        else:
            type_pool = ["studio", "1br", "2br", "3br"]
            types = random.choices(type_pool, k=num_flats)

        left_count = (num_flats + 1) // 2

        # Left side flats (first half)
        for i in range(left_count):
            flat = Flat(
                flat_id=f"{level}{chr(65 + i)}",
                flat_type=types[i],
                floor=level,
                config=self.config,
                side="left",
            )
            flats.append(flat)

        # Right side flats (remaining)
        for i in range(num_flats - left_count):
            types_idx = left_count + i
            flat = Flat(
                flat_id=f"{level}{chr(65 + types_idx)}",
                flat_type=types[types_idx],
                floor=level,
                config=self.config,
                side="right",
            )
            flats.append(flat)

        return flats

    # ── Lift Dispatch Interface ─────────────────────────────────────────

    def call_lift_to(self, floor: int, direction: str = "down") -> None:
        """Convenience: route a hall call through the lift system."""
        self.lift_system.handle_hall_call(floor, direction)

    # ── Update ───────────────────────────────────────────────────────────

    def update(self, dt: float) -> None:
        """Update all dynamic systems in the building."""
        self.lift_system.update(dt)
        for person in self.population:
            person.update(dt, self, self.lift_system.lifts)

    # ── Drawing ──────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface, clock, camera: 'Camera' = None) -> None:
        """Render the building cross-section with correct depth ordering.

        Draw order (back to front):
          1. Shafts + building frame
          2. Floors + flats (the "walls")
          3. Lift cars (on TOP of floors — visible inside the shaft)
          4. People (on top of everything)

        Args:
            screen: Pygame surface to draw on.
            clock: WorldClock for time-of-day effects.
            camera: Camera for viewport offset. None = no offset.
        """
        self._cam_y = camera.y if camera else 0.0
        self._cam = camera
        self._screen_h = screen.get_height()

        self._draw_building_frame(screen)
        self._draw_shafts(screen)
        self._draw_floors_and_flats(screen)  # Floors first (behind lifts)
        self.lift_system.draw(screen, camera)  # Lifts on TOP of floors
        self._draw_people(screen)               # People on top

    # ── Drawing: Background ──────────────────────────────────────────────

    def _draw_building_frame(self, screen: pygame.Surface) -> None:
        """Draw the building exterior walls with camera offset."""
        cfg = self.config
        cam_y = self._cam_y
        top = cfg.BUILDING_Y - cam_y
        building_h = cfg.NUM_FLOORS * cfg.FLOOR_HEIGHT

        rect = pygame.Rect(
            cfg.BUILDING_X,
            int(top),
            cfg.BUILDING_WIDTH,
            building_h,
        )
        # Building background (only if visible)
        if rect.bottom > -building_h and rect.top < self._screen_h:
            pygame.draw.rect(screen, (50, 50, 60), rect)
            # Outer walls
            pygame.draw.rect(screen, (90, 90, 110), rect, width=cfg.BUILDING_WALL_THICKNESS)

    # ── Drawing: Shafts ─────────────────────────────────────────────────

    def _draw_shafts(self, screen: pygame.Surface) -> None:
        """Draw the centered lift shaft area with camera offset."""
        cfg = self.config
        cam_y = self._cam_y
        building_h = cfg.NUM_FLOORS * cfg.FLOOR_HEIGHT
        top = cfg.BUILDING_Y - cam_y

        shaft_x = cfg.LIFT_SHAFT_X
        shaft_w = cfg.LIFT_SHAFT_WIDTH

        shaft_rect = pygame.Rect(
            shaft_x,
            int(top),
            shaft_w,
            building_h,
        )

        # Only draw if visible
        if shaft_rect.bottom > -building_h and shaft_rect.top < self._screen_h:
            # Dark shaft background
            pygame.draw.rect(screen, (25, 25, 35), shaft_rect)
            # Shaft border
            pygame.draw.rect(screen, (60, 60, 80), shaft_rect, width=2)

            # Draw vertical guide lines for each lift
            cell_w = shaft_w // cfg.NUM_LIFTS
            for i in range(1, cfg.NUM_LIFTS):
                gx = shaft_x + i * cell_w
                pygame.draw.line(
                    screen, (40, 40, 55),
                    (gx, top),
                    (gx, top + building_h),
                    width=1,
                )

    # ── Drawing: Floors & Flats ─────────────────────────────────────────

    def _draw_floors_and_flats(self, screen: pygame.Surface) -> None:
        """Draw floor separator lines, flat rectangles, and corridor gaps.

        Layout: [wall] [left flats] [gap] [SHAFT] [gap] [right flats] [wall]
        Floor lines span the interior but skip the shaft opening.
        All Y coordinates offset by camera for viewport scrolling.
        On-screen culling: floors outside viewport are skipped.
        """
        cfg = self.config
        cam_y = self._cam_y
        screen_h = self._screen_h
        wall = cfg.BUILDING_WALL_THICKNESS
        shaft_x = cfg.LIFT_SHAFT_X
        shaft_w = cfg.LIFT_SHAFT_WIDTH
        shaft_right = shaft_x + shaft_w
        interior_left = cfg.BUILDING_X + wall
        interior_right = cfg.BUILDING_X + cfg.BUILDING_WIDTH - wall

        for floor in self.floors:
            world_y = cfg.BUILDING_Y + (cfg.NUM_FLOORS - 1 - floor.level) * cfg.FLOOR_HEIGHT
            screen_y = world_y - cam_y

            # ── Culling: skip floors off screen + margin ─────────────
            if screen_y + cfg.FLOOR_HEIGHT < -60 or screen_y > screen_h + 60:
                continue

            # ── Floor separator lines (skip shaft opening) ──────────
            sy = int(screen_y)
            # Left segment: wall → shaft left edge
            pygame.draw.line(
                screen, (110, 110, 130),
                (cfg.BUILDING_X, sy),
                (shaft_x, sy),
                width=cfg.FLOOR_LINE_HEIGHT,
            )
            # Right segment: shaft right edge → wall
            pygame.draw.line(
                screen, (110, 110, 130),
                (shaft_right, sy),
                (cfg.BUILDING_X + cfg.BUILDING_WIDTH, sy),
                width=cfg.FLOOR_LINE_HEIGHT,
            )

            # ── Corridor/landing areas ───────────────────────────────
            # Left corridor: between left flats and shaft
            corridor_left = pygame.Rect(
                cfg.LEFT_FLATS_X + cfg.LEFT_FLATS_WIDTH,
                sy,
                shaft_x - (cfg.LEFT_FLATS_X + cfg.LEFT_FLATS_WIDTH),
                cfg.FLOOR_HEIGHT,
            )
            pygame.draw.rect(screen, (65, 65, 75), corridor_left)

            # Right corridor: between shaft and right flats
            corridor_right = pygame.Rect(
                shaft_right,
                sy,
                interior_right - shaft_right,
                cfg.FLOOR_HEIGHT,
            )
            pygame.draw.rect(screen, (65, 65, 75), corridor_right)

            # ── Draw flats (skip ground floor — lobby) ──────────────
            if floor.level == 0:
                # Ground floor lobby label
                if hasattr(self, '_font'):
                    label = self._font.render("LOBBY", True, (150, 150, 170))
                    screen.blit(label, (cfg.BUILDING_X + 20, sy + 20))
                continue

            for flat in floor.flats:
                rect = flat.get_rect(
                    floor.flats.index(flat),
                    len(floor.flats),
                )
                # Offset by camera
                rect.y = int(rect.y - cam_y)

                # Flat body colour
                colour = cfg.FLAT_COLORS.get(flat.flat_type, (150, 150, 150))
                pygame.draw.rect(screen, colour, rect, border_radius=2)

                # Flat border
                pygame.draw.rect(screen, (80, 80, 100), rect, width=1, border_radius=2)

                # Door indicator
                door_rect = pygame.Rect(
                    rect.centerx - 6,
                    rect.bottom - 12,
                    12,
                    12,
                )
                occupant_colour = (100, 200, 100) if flat.occupants else (100, 100, 100)
                pygame.draw.rect(screen, occupant_colour, door_rect, border_radius=1)

                # Flat label
                if hasattr(self, '_font'):
                    label = self._font.render(flat.flat_id, True, (220, 220, 230))
                    screen.blit(label, (rect.x + 4, rect.y + 4))

                # Debug: occupant count
                occ_count = len(flat.occupants)
                occ_text = f"{occ_count}"
                occ_surf = self._font.render(occ_text, True, (255, 255, 200))
                screen.blit(occ_surf, (rect.right - occ_surf.get_width() - 4, rect.y + 4))

    # ── Drawing: People ─────────────────────────────────────────────────

    def _draw_people(self, screen: pygame.Surface) -> None:
        """Draw all visible people, offset by camera, with culling."""
        font = getattr(self, '_font', None)
        cam_y = self._cam_y
        screen_h = self._screen_h
        for person in self.population:
            # Quick Y-visibility check before drawing
            py = person.py
            if py < cam_y - 100 or py > cam_y + screen_h + 100:
                continue
            person.draw(screen, font, camera=self._cam)
