"""
LiftSim V2 — SimulationEngine
===============================
The "God Object" — owns the GameState machine, WorldClock, Config,
Building, and Menu. Routes between MENU → GENERATING → SIMULATING.

Lifecycle:
  1. SimulationEngine(config)        # Construct
  2. engine.run()                    # Main loop
  3. (window closes) → cleanup
"""

from __future__ import annotations

import sys
import os
from typing import Optional

import pygame

_sys_path = os.path.dirname(os.path.abspath(__file__))
if _sys_path not in sys.path:
    sys.path.insert(0, _sys_path)

from config import SimulationConfig
from clock import WorldClock
from building import Building
from state import GameState
from settings import SimSettings, calc_floor_height, calc_building_width
from camera import Camera
from ui.theme import Theme
from ui.menu import MenuScreen
from rendering.effects import draw_darken_overlay, GenerationAnimation


class SimulationEngine:
    """Top-level controller for the LiftSim simulation.

    Args:
        config: SimulationConfig instance (defaults if None).
    """

    def __init__(self, config: Optional[SimulationConfig] = None) -> None:
        self.config: SimulationConfig = config or SimulationConfig()
        self.settings: SimSettings = SimSettings()
        # Propagate config values that override SimSettings defaults
        if config is not None:
            self.settings.num_floors = self.config.NUM_FLOORS
            self.settings.num_lifts = self.config.NUM_LIFTS
            self.settings.flats_per_floor = self.config.FLATS_PER_FLOOR
        self.clock: WorldClock = WorldClock(self.config.TIME_SCALE)
        self.theme: Theme = Theme()
        self.state: GameState = GameState.MENU

        self.running: bool = False
        self.screen: Optional[pygame.Surface] = None
        self._clock: Optional[pygame.time.Clock] = None
        self._font: Optional[pygame.font.Font] = None

        # ── Components (created later) ─────────────────────────────
        self.building: Optional[Building] = None
        self.menu: Optional[MenuScreen] = None
        self.generation: Optional[GenerationAnimation] = None
        self.camera: Optional[Camera] = None
        self._last_think_minute: int = -1
        self._build_h: int = 0  # Total building height for scroll clamping
        self._follow_btn_rects: list = []  # (rect, lift_idx|-1) for click tracking

        # ── Mouse Drag Scrolling ───────────────────────────────────
        self._drag_start_y: Optional[float] = None
        self._drag_cam_start_y: Optional[float] = None

    # ── Setup / Teardown ────────────────────────────────────────────────

    def setup(self) -> None:
        """Initialise Pygame, create window, build menu."""
        pygame.init()
        self.screen = pygame.display.set_mode(
            (self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT)
        )
        pygame.display.set_caption("LiftSim V2")
        self._clock = pygame.time.Clock()
        self._font = pygame.font.Font(None, 28)
        self.running = True

        # Build the menu screen
        self.menu = MenuScreen(self.settings, self.theme, self._on_start_clicked)

    def cleanup(self) -> None:
        """Shut down Pygame cleanly."""
        pygame.quit()
        self.running = False

    # ── State Transitions ───────────────────────────────────────────────

    def _on_start_clicked(self) -> None:
        """User clicked START button → switch to GENERATING then SIMULATING."""
        self.state = GameState.GENERATING
        self.generation = GenerationAnimation(duration=1.0)

    def _finish_generation(self) -> None:
        """Generation animation complete — build the simulation and switch."""
        self.rebuild()
        self.state = GameState.SIMULATING

    def rebuild(self) -> None:
        """Destroy old building, create new one from current settings.

        Computes the full building layout:
            [wall] [left flats] [gap] [LIFT SHAFT] [gap] [right flats] [wall]
        """
        s = self.settings
        sw, sh = self.config.SCREEN_WIDTH, self.config.SCREEN_HEIGHT

        # Calculate dynamic floor height
        floor_h = calc_floor_height(s.num_floors, sh)
        wt = self.config.BUILDING_WALL_THICKNESS
        gap = self.config.GAP_WIDTH
        fw = self.config.FLAT_WIDTH

        # Split flats left/right
        left_count = (s.flats_per_floor + 1) // 2
        right_count = s.flats_per_floor // 2

        left_flats_w = left_count * fw
        right_flats_w = right_count * fw
        shaft_w = s.num_lifts * self.config.LIFT_WIDTH + 20

        # Total building width
        bldg_w = wt + left_flats_w + gap + shaft_w + gap + right_flats_w + wt

        # Compute positions (centre the building on screen)
        bldg_x = max(40, (sw - bldg_w) // 2)

        shaft_x = bldg_x + wt + left_flats_w + gap
        left_flats_x = bldg_x + wt
        right_flats_x = shaft_x + shaft_w + gap

        # Update config with dynamic values
        self.config.FLOOR_HEIGHT = floor_h
        self.config.NUM_FLOORS = s.num_floors
        self.config.FLATS_PER_FLOOR = s.flats_per_floor
        self.config.NUM_LIFTS = s.num_lifts
        self.config.BUILDING_X = bldg_x
        self.config.BUILDING_WIDTH = bldg_w
        self.config.LIFT_SPEED = s.lift_speed
        self.config.LIFT_CAPACITY = s.lift_capacity
        self.config.LIFT_DOOR_DWELL = s.door_dwell

        # Layout positions
        self.config.LIFT_SHAFT_X = shaft_x
        self.config.LIFT_SHAFT_WIDTH = shaft_w
        self.config.LEFT_FLATS_X = left_flats_x
        self.config.LEFT_FLATS_WIDTH = left_flats_w
        self.config.RIGHT_FLATS_X = right_flats_x
        self.config.RIGHT_FLATS_WIDTH = right_flats_w

        # Fixed top margin — building can now scroll if taller than screen
        self.config.BUILDING_Y = 30

        # Initialise camera (new: scrollable viewport)
        total_building_h = s.num_floors * floor_h + self.config.LOBBY_HEIGHT
        self._build_h = total_building_h
        max_y = max(0, total_building_h + self.config.BUILDING_Y - sh + 10)
        self.camera = Camera(max_y=max_y)
        self.camera.y = float(max_y)  # Start at bottom, lobby visible
        self.config.BUILDING_HEIGHT = total_building_h

        # Build fresh
        self.building = Building(self.config)
        self.building._font = self._font
        self.building.lift_system.set_debug_font(self._font)

        # Populate with residents
        self.building.populate(density=s.population_density)

        # Reset clock to start of day
        self.clock.reset()
        # Advance clock to start_hour minutes
        self.clock.total_seconds = s.start_hour * 3600.0

        # Initial think so people check their schedule immediately
        self._last_think_minute = -1

    # ── Event Handling ──────────────────────────────────────────────────

    def handle_events(self) -> None:
        """Process all pending Pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            # ── ESC key: always handled early ──────────────────────────
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                if self.state == GameState.SIMULATING:
                    self.state = GameState.MENU
                return

            # ── F1-F4: lift follow hotkeys (sim-only) ─────────────────
            if (event.type == pygame.KEYDOWN and self.state == GameState.SIMULATING
                    and self.camera and self.building):
                follow_map = {pygame.K_F1: 0, pygame.K_F2: 1, pygame.K_F3: 2, pygame.K_F4: 3}
                if event.key in follow_map:
                    lift_idx = follow_map[event.key]
                    if lift_idx < self.config.NUM_LIFTS:
                        self.camera.follow_lift(lift_idx)
                    else:
                        # F-key > lift count = free scroll
                        self.camera.free_scroll()
                    return

            # ── Route to active state ─────────────────────────────────
            if self.state == GameState.MENU and self.menu:
                self.menu.handle_event(event)

            elif self.state == GameState.SIMULATING:
                self._handle_sim_keydown(event)
                if event.type == pygame.MOUSEWHEEL:
                    self._handle_sim_mousewheel(event)
                if event.type == pygame.MOUSEBUTTONDOWN:
                    self._handle_sim_mousedown(event)
                if event.type == pygame.MOUSEBUTTONUP:
                    self._handle_sim_mouseup(event)
                if event.type == pygame.MOUSEMOTION:
                    self._handle_sim_mousemotion(event)

    def _handle_sim_keydown(self, event: pygame.event.Event) -> None:
        """Handle simulation keyboard input."""
        if event.type != pygame.KEYDOWN:
            return

        speed_map = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 4}
        if event.key in speed_map:
            self.clock.time_scale = speed_map[event.key]
        elif event.key == pygame.K_SPACE:
            self.clock.paused = not self.clock.paused
        elif event.key == pygame.K_r:
            self.rebuild()

        # ── Camera / Scroll controls ────────────────────────────────
        elif event.key == pygame.K_UP or event.key == pygame.K_w:
            if self.camera:
                self.camera.scroll(-self.camera.SCROLL_STEP, self.config.SCREEN_HEIGHT, self._build_h)
        elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
            if self.camera:
                self.camera.scroll(self.camera.SCROLL_STEP, self.config.SCREEN_HEIGHT, self._build_h)
        elif event.key == pygame.K_f:
            if self.camera:
                self.camera.follow_lift_id = -1  # Free scroll
        elif event.key == pygame.K_ESCAPE:
            # Already handled above in main event loop
            pass

    def _handle_sim_mousewheel(self, event: pygame.event.Event) -> None:
        """Handle mouse wheel scroll (sets camera to free mode)."""
        if self.camera:
            self.camera.scroll(-event.y * 15, self.config.SCREEN_HEIGHT, self._build_h)

    # ── Game Loop ───────────────────────────────────────────────────────


    def _handle_sim_mouseclick(self, event: pygame.event.Event) -> bool:
        """Handle mouse click on follow bar buttons.

        Returns True if a button was clicked (consumed), False otherwise.
        """
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if not self.camera or not self._follow_btn_rects:
            return False
        mx, my = event.pos
        for rect, target in self._follow_btn_rects:
            if rect.collidepoint(mx, my):
                if target < 0:
                    self.camera.free_scroll()
                else:
                    self.camera.follow_lift(target)
                return True
        return False

    def _handle_sim_mousedown(self, event: pygame.event.Event) -> None:
        """Handle mouse button down in simulation mode."""
        if event.button == 1:
            if not self._handle_sim_mouseclick(event):
                self._start_drag(event.pos)
        elif event.button == 3:
            if self.camera:
                self.camera.free_scroll()

    def _handle_sim_mouseup(self, event: pygame.event.Event) -> None:
        """Handle mouse button up in simulation mode."""
        if event.button == 1:
            self._end_drag()

    def _handle_sim_mousemotion(self, event: pygame.event.Event) -> None:
        """Handle mouse movement in simulation mode."""
        self._handle_drag(event)

    # ── Mouse Drag Scrolling ────────────────────────────────────────────

    def _start_drag(self, pos: tuple) -> None:
        """Begin a mouse drag scroll."""
        if not self.camera:
            return
        self._drag_start_y = float(pos[1])
        self._drag_cam_start_y = self.camera.y
        self.camera.free_scroll()  # Switch to free mode while dragging

    def _handle_drag(self, event: pygame.event.Event) -> None:
        """Update camera position based on mouse drag delta."""
        if (self._drag_start_y is None or self._drag_cam_start_y is None
                or not self.camera):
            return
        dy = float(event.pos[1]) - self._drag_start_y
        # Inverted: dragging DOWN (dy+) scrolls UP (camera_y-)
        new_y = self._drag_cam_start_y - dy
        clamped = max(self.camera.MIN_Y, min(new_y, self.camera.MAX_Y))
        self.camera.y = clamped

    def _end_drag(self) -> None:
        """End the mouse drag."""
        self._drag_start_y = None
        self._drag_cam_start_y = None

    def update(self, dt: float) -> None:
        """Advance simulation logic based on current state."""
        if self.state == GameState.GENERATING and self.generation:
            self.generation.update(dt)
            if self.generation.done:
                self._finish_generation()

        elif self.state == GameState.SIMULATING:
            self.clock.tick(dt)
            if self.building:
                # ── Camera follow update ─────────────────────────
                if self.camera:
                    self.camera.update(
                        dt, self.building.lift_system.lifts,
                        self.config.SCREEN_HEIGHT, self.config.LIFT_HEIGHT,
                    )

                # ── Think cycle (once per sim-minute) ────────────
                current_min = self.clock.get_total_minutes()
                if current_min != self._last_think_minute:
                    self._last_think_minute = current_min
                    self.building.think_all(self.clock)

                self.building.update(dt)

    def draw(self) -> None:
        """Render the current state to the screen."""
        if self.screen is None:
            return

        # ── Always draw sky background ─────────────────────────────
        hour = self.clock.sim_hour
        if 6 <= hour < 8:
            sky = self.config.SKY_COLORS["dawn"]
        elif 8 <= hour < 17:
            sky = self.config.SKY_COLORS["day"]
        elif 17 <= hour < 20:
            sky = self.config.SKY_COLORS["dusk"]
        else:
            sky = self.config.SKY_COLORS["night"]
        self.screen.fill(sky)

        camera = self.camera  # May be None during menu/generating

        # ── SIMULATING: draw the building + HUD ────────────────────
        if self.state == GameState.SIMULATING and self.building:
            self.building.draw(self.screen, self.clock, camera=camera)
            self._draw_hud()

        # ── MENU: darken overlay + menu on top ─────────────────────
        if self.state == GameState.MENU and self.menu:
            # Still draw building underneath for a nice background effect
            if self.building:
                self.building.draw(self.screen, self.clock, camera=camera)
            draw_darken_overlay(self.screen, self.theme)
            self.menu.draw(self.screen)

        # ── GENERATING: dark overlay + animation ───────────────────
        if self.state == GameState.GENERATING and self.generation:
            if self.building:
                self.building.draw(self.screen, self.clock, camera=camera)
            draw_darken_overlay(self.screen, self.theme)
            self.generation.draw(self.screen, self.theme)

        pygame.display.flip()

    def _draw_hud(self) -> None:
        """Draw the simulation HUD overlay."""
        self._follow_btn_rects.clear()
        cfg = self.config
        cam = self.camera

        # ── Right HUD panel ─────────────────────────────────────────────
        lines = [
            f"{self.clock.get_full_time_str()}  Day {self.clock.sim_day}",
            f"Speed: {self.clock.time_scale}x  "
            f"{'PAUSED' if self.clock.paused else 'RUNNING'}",
            f"1/2/3 Speed · SPACE Pause · R Rebuild · ESC Menu",
        ]
        y = 8
        for line in lines:
            colour = (230, 230, 240)
            if "PAUSED" in line:
                colour = (255, 220, 80)
            elif "RUNNING" in line:
                colour = (100, 255, 100)
            elif "Speed" in line and "x" in line:
                colour = (180, 180, 200)

            if self._font:
                surf = self._font.render(line, True, colour)
                x = cfg.SCREEN_WIDTH - surf.get_width() - 10
                self.screen.blit(surf, (x, y))
            y += 22

        # ── Follow Bar (bottom-left) ────────────────────────────────────
        if cam and self._font:
            bar_x, bar_y = 10, cfg.SCREEN_HEIGHT - 60
            # Title
            title_surf = self._font.render("Follow:", True, (200, 200, 220))
            self.screen.blit(title_surf, (bar_x, bar_y))
            bx = bar_x + title_surf.get_width() + 8

            # Button for each lift
            for i in range(cfg.NUM_LIFTS):
                active = (cam.follow_lift_id == i)
                btn_colour = (80, 180, 255) if active else (60, 60, 80)
                text = f" L{i+1} "
                surf = self._font.render(text, True, (255, 255, 255))
                bg_rect = surf.get_rect(topleft=(bx, bar_y))
                bg_rect.inflate_ip(6, 2)
                pygame.draw.rect(self.screen, btn_colour, bg_rect, border_radius=3)
                self.screen.blit(surf, (bx + 3, bar_y))
                self._follow_btn_rects.append((bg_rect.copy(), i))
                bx += bg_rect.width + 4

            # FREE button
            free_active = (cam.follow_lift_id == -1)
            btn_colour = (120, 120, 120) if free_active else (60, 60, 80)
            surf = self._font.render(" FREE ", True, (255, 255, 255))
            bg_rect = surf.get_rect(topleft=(bx, bar_y))
            bg_rect.inflate_ip(6, 2)
            pygame.draw.rect(self.screen, btn_colour, bg_rect, border_radius=3)
            self.screen.blit(surf, (bx + 3, bar_y))
            self._follow_btn_rects.append((bg_rect.copy(), -1))

            # ── Scroll indicators ────────────────────────────────────
            if cam.y > cam.MIN_Y + 2:  # Can scroll UP → ▲ at top
                arrow_surf = self._font.render("\u25B2", True, (255, 200, 100))
                self.screen.blit(arrow_surf, (cfg.SCREEN_WIDTH // 2 - 10, 8))
            if cam.y < cam.MAX_Y - 2:  # Can scroll DOWN → ▼ at bottom
                arrow_surf = self._font.render("\u25BC", True, (255, 200, 100))
                self.screen.blit(arrow_surf, (cfg.SCREEN_WIDTH // 2 - 10, cfg.SCREEN_HEIGHT - 35))

        # ── Controls hint (at bottom center) ────────────────────────────
        if self._font:
            hint = "F1-F4 Follow · F Free · Alt+Scroll"
            hint_surf = self._font.render(hint, True, (140, 140, 160))
            hint_x = (cfg.SCREEN_WIDTH - hint_surf.get_width()) // 2
            hint_y = cfg.SCREEN_HEIGHT - hint_surf.get_height() - 8
            self.screen.blit(hint_surf, (hint_x, hint_y))

    # ── Main Loop ───────────────────────────────────────────────────────

    def run(self) -> None:
        """Main simulation loop — runs until window is closed."""
        self.setup()

        try:
            while self.running:
                dt = self._clock.tick(self.config.FPS) / 1000.0
                self.handle_events()
                self.update(dt)
                self.draw()
        finally:
            self.cleanup()

    # ── Entry Point ─────────────────────────────────────────────────────

    @staticmethod
    def launch(config: Optional[SimulationConfig] = None) -> None:
        """Convenience static method to create and run the engine."""
        engine = SimulationEngine(config)
        engine.run()
