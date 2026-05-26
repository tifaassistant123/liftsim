"""
LiftSim V2 — Menu Screen
=========================
Full settings UI with live building preview and Start button.
"""

from __future__ import annotations

from typing import Callable

import pygame

from ui.theme import Theme
from ui.widgets import Button, Slider
from settings import SimSettings


class MenuScreen:
    """The main settings/menu screen shown before simulation starts.

    Owns all slider widgets and the Start button.
    Provides a live preview of the building configuration.
    """

    def __init__(self, settings: SimSettings, theme: Theme,
                 on_start: Callable[[], None]) -> None:
        self.settings = settings
        self.theme = theme
        self.on_start = on_start
        self.widgets: list = []  # All interactive widgets
        self._build_ui()

    # ── Layout ──────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Create all UI widgets based on current screen dimensions."""
        self.widgets.clear()

        sw, sh = 1024, 1024  # we know the screen size
        t = self.theme

        # Main panel centred on screen
        panel_w, panel_h = 860, 800
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        self.panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        # ── Title ───────────────────────────────────────────────────
        self._title_text = "LiftSim V2  —  Simulation Setup"
        self._title_y = panel_y + t.MARGIN

        # ── Preview area (left column) ──────────────────────────────
        preview_x = panel_x + t.MARGIN
        preview_y = self._title_y + t.TITLE_HEIGHT + t.PADDING
        preview_w = 320
        preview_h = panel_h - (preview_y - panel_y) - t.MARGIN - t.BUTTON_HEIGHT - t.PADDING
        self.preview_rect = pygame.Rect(preview_x, preview_y, preview_w, preview_h)

        # ── Controls (right column) ─────────────────────────────────
        controls_x = preview_x + preview_w + t.PADDING * 2
        controls_w = panel_w - preview_w - t.MARGIN * 2 - t.PADDING * 3
        control_y = preview_y
        control_h_per = (preview_h - t.WIDGET_GAP * 5) // 5

        # Sliders
        def _make_slider(label: str, val: float, min_v: float, max_v: float,
                         step: float, decimals: int = 0, suffix: str = "") -> Slider:
            return Slider(
                rect=pygame.Rect(controls_x, control_y, controls_w, t.SLIDER_HEIGHT),
                min_val=min_v, max_val=max_v, default=val, step=step,
                label=label, on_change=lambda v: None,
                theme=t, display_decimals=decimals, suffix=suffix,
            )

        self.slider_floors = _make_slider("Floors", self.settings.num_floors, 4, 30, 1, 0, "")
        self.slider_floors.on_change = self._on_floors
        control_y += control_h_per + t.WIDGET_GAP

        self.slider_flats = _make_slider("Flats/Floor", self.settings.flats_per_floor, 1, 6, 1, 0, "")
        self.slider_flats.on_change = self._on_flats
        control_y += control_h_per + t.WIDGET_GAP

        self.slider_lifts = _make_slider("Lifts", self.settings.num_lifts, 1, 4, 1, 0, "")
        self.slider_lifts.on_change = self._on_lifts
        control_y += control_h_per + t.WIDGET_GAP

        self.slider_speed = _make_slider("Lift Speed", self.settings.lift_speed, 0.5, 4.0, 0.5, 1, "x")
        self.slider_speed.on_change = self._on_speed
        control_y += control_h_per + t.WIDGET_GAP

        self.slider_density = _make_slider("Density", self.settings.population_density * 100, 10, 100, 5, 0, "%")
        self.slider_density.on_change = self._on_density
        control_y += control_h_per + t.WIDGET_GAP

        # Collect all widgets
        all_sliders = [self.slider_floors, self.slider_flats, self.slider_lifts,
                       self.slider_speed, self.slider_density]
        self.widgets.extend(all_sliders)

        # ── Start Button ───────────────────────────────────────────
        btn_w = 220
        btn_h = t.BUTTON_HEIGHT
        btn_x = controls_x + (controls_w - btn_w) // 2
        btn_y = self.preview_rect.bottom - t.BUTTON_HEIGHT
        # Actually, put it below the controls
        btn_y = control_y + t.PADDING + 10
        # But keep it in the controls column area
        btn_x = controls_x + (controls_w - btn_w) // 2

        self.start_btn = Button(
            rect=pygame.Rect(btn_x, btn_y, btn_w, btn_h),
            text="START SIMULATION",
            on_click=self.on_start,
            theme=t,
            is_start=True,
        )
        self.widgets.append(self.start_btn)

    # ── Callbacks ───────────────────────────────────────────────────────

    def _on_floors(self, v: float) -> None:
        self.settings.num_floors = int(v)

    def _on_flats(self, v: float) -> None:
        self.settings.flats_per_floor = int(v)

    def _on_lifts(self, v: float) -> None:
        self.settings.num_lifts = int(v)

    def _on_speed(self, v: float) -> None:
        self.settings.lift_speed = v

    def _on_density(self, v: float) -> None:
        self.settings.population_density = v / 100.0

    # ── Event Handling ──────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Route events to all widgets. Returns True if consumed."""
        for w in self.widgets:
            if w.handle_event(event):
                return True
        return False

    # ── Drawing ─────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface) -> None:
        """Render the full menu screen."""
        t = self.theme

        # ── Main panel ─────────────────────────────────────────────
        # Outer panel
        pygame.draw.rect(surface, t.panel_bg, self.panel_rect, border_radius=12)
        pygame.draw.rect(surface, t.panel_border, self.panel_rect,
                         width=2, border_radius=12)

        # ── Title ──────────────────────────────────────────────────
        title_label = t.font_title.render(self._title_text, True, t.text_primary)
        tx = self.panel_rect.centerx - title_label.get_width() // 2
        surface.blit(title_label, (tx, self._title_y))

        # ── Preview ────────────────────────────────────────────────
        self._draw_preview(surface)

        # ── Slider labels (re-draw active value labels) ────────────
        self.slider_floors.draw(surface)
        self.slider_flats.draw(surface)
        self.slider_lifts.draw(surface)
        self.slider_speed.draw(surface)
        self.slider_density.draw(surface)

        # ── Start button ───────────────────────────────────────────
        self.start_btn.draw(surface)

    def _draw_preview(self, surface: pygame.Surface) -> None:
        """Draw a miniature building silhouette showing current config."""
        t = self.theme
        pr = self.preview_rect

        # Preview background
        pygame.draw.rect(surface, (15, 16, 22), pr, border_radius=6)
        pygame.draw.rect(surface, t.panel_border, pr, width=1, border_radius=6)

        nf = self.settings.num_floors
        nflats = self.settings.flats_per_floor
        nlifts = self.settings.num_lifts

        # Scale the building to fit the preview
        margin = 16
        p_w = pr.width - margin * 2
        p_h = pr.height - margin * 2

        # Building frame
        b_x = pr.x + margin
        b_y = pr.y + margin + 20  # leave room for "10F" label
        b_w = p_w
        b_h = min(p_h - 24, nf * 12)  # 12px per floor cap
        floor_h = b_h // max(nf, 1)

        # Floor rectangles (top-down)
        for i in range(nf):
            fy = b_y + i * floor_h
            fh = max(floor_h - 1, 2)

            # Floor background
            pygame.draw.rect(surface, t.preview_floor,
                             (b_x, fy, b_w, fh), border_radius=1)

            # Flat divisions (if not ground)
            if i > 0 and nflats > 1:
                flat_w = b_w // nflats
                for f in range(1, nflats):
                    fx = b_x + f * flat_w
                    pygame.draw.line(surface, (40, 42, 55),
                                     (fx, fy), (fx, fy + fh), width=1)

        # Lift shaft (right side)
        shaft_w = min(30, b_w // 4)
        shaft_x = b_x + b_w - shaft_w
        pygame.draw.rect(surface, t.preview_shaft,
                         (shaft_x, b_y, shaft_w, b_h - 1))

        # Lift cars
        for li in range(nlifts):
            cell_w = shaft_w // nlifts
            lx = shaft_x + li * cell_w + 2
            ly = b_y + 2
            lw = max(cell_w - 4, 4)
            lh = floor_h - 4
            pygame.draw.rect(surface, t.preview_lift,
                             (lx, ly, lw, lh), border_radius=1)

        # Ground floor label
        ground_y = b_y + (nf - 1) * floor_h
        if t.font_small:
            g_label = t.font_small.render("G", True, t.text_secondary)
            surface.blit(g_label, (b_x + 4, ground_y + 2))

        # Top label
        if t.font_small:
            info = f"{nf}F  |  {nflats} flat/floor  |  {nlifts} lift{'s' if nlifts > 1 else ''}"
            info_surf = t.font_small.render(info, True, t.text_accent)
            ix = pr.centerx - info_surf.get_width() // 2
            surface.blit(info_surf, (ix, pr.y + 4))
