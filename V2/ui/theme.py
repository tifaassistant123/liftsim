"""
LiftSim V2 — UI Theme
======================
Central colour palette, font loading, and spacing constants.
All UI widgets reference this, making theme-switching trivial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

import pygame

Colour = Tuple[int, int, int]


@dataclass
class Theme:
    """Named colour palette for the entire UI system."""

    # ── Surfaces ────────────────────────────────────────────────────────
    panel_bg: Colour = (20, 22, 30)
    panel_border: Colour = (60, 65, 85)
    overlay: Colour = (0, 0, 0)

    # ── Text ────────────────────────────────────────────────────────────
    text_primary: Colour = (230, 230, 240)
    text_secondary: Colour = (160, 165, 180)
    text_accent: Colour = (100, 200, 255)

    # ── Controls ────────────────────────────────────────────────────────
    button_bg: Colour = (45, 55, 90)
    button_hover: Colour = (60, 75, 120)
    button_text: Colour = (230, 230, 240)

    start_bg: Colour = (40, 120, 70)
    start_hover: Colour = (55, 155, 90)

    slider_track: Colour = (40, 42, 55)
    slider_fill: Colour = (60, 130, 220)
    slider_thumb: Colour = (100, 180, 255)

    # ── Building Preview ────────────────────────────────────────────────
    preview_floor: Colour = (55, 58, 70)
    preview_shaft: Colour = (30, 32, 42)
    preview_lift: Colour = (80, 150, 240)

    # ── Generation ──────────────────────────────────────────────────────
    gen_text: Colour = (255, 220, 100)

    # ── Screen ──────────────────────────────────────────────────────────
    OVERLAY_ALPHA: int = 180  # 0–255

    # ── Spacing ─────────────────────────────────────────────────────────
    PADDING: int = 14
    MARGIN: int = 20
    WIDGET_GAP: int = 10
    SLIDER_HEIGHT: int = 50
    BUTTON_HEIGHT: int = 48
    TITLE_HEIGHT: int = 50
    FONT_SIZE_TITLE: int = 32
    FONT_SIZE_BODY: int = 22
    FONT_SIZE_SMALL: int = 16

    # Font caches (lazy-loaded)
    _fonts: Dict[str, pygame.font.Font] = field(default_factory=dict, repr=False)

    def get_font(self, size: int) -> pygame.font.Font:
        """Get or create a cached font."""
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(None, size)
        return self._fonts[size]

    @property
    def font_title(self) -> pygame.font.Font:
        return self.get_font(self.FONT_SIZE_TITLE)

    @property
    def font_body(self) -> pygame.font.Font:
        return self.get_font(self.FONT_SIZE_BODY)

    @property
    def font_small(self) -> pygame.font.Font:
        return self.get_font(self.FONT_SIZE_SMALL)
