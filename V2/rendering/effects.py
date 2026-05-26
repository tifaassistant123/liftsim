"""
LiftSim V2 — Visual Effects
=============================
Darken overlay, generation animation, and other screen effects.
"""

from __future__ import annotations

import pygame

from ui.theme import Theme


def draw_darken_overlay(surface: pygame.Surface, theme: Theme) -> None:
    """Draw a semi-transparent dark overlay over the entire screen."""
    overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    overlay.fill((*theme.overlay, theme.OVERLAY_ALPHA))
    surface.blit(overlay, (0, 0))


class GenerationAnimation:
    """Brief construction animation shown during GENERATING state."""

    def __init__(self, duration: float = 1.0) -> None:
        self.duration = duration
        self.elapsed = 0.0
        self.done = False

    def update(self, dt: float) -> None:
        self.elapsed += dt
        if self.elapsed >= self.duration:
            self.done = True

    def reset(self) -> None:
        self.elapsed = 0.0
        self.done = False

    def draw(self, surface: pygame.Surface, theme: Theme) -> None:
        """Draw the generating overlay centred on screen."""
        dots = "." * (int(self.elapsed * 4) % 6)
        text = f"Constructing building{dots}"
        font = theme.font_title
        surf = font.render(text, True, theme.gen_text)
        x = (surface.get_width() - surf.get_width()) // 2
        y = surface.get_height() // 2
        surface.blit(surf, (x, y))

        # Progress bar
        bar_w = 300
        bar_h = 6
        bx = (surface.get_width() - bar_w) // 2
        by = y + 40
        progress = min(self.elapsed / self.duration, 1.0)

        # Background
        pygame.draw.rect(surface, (40, 42, 55),
                         (bx, by, bar_w, bar_h), border_radius=3)
        # Fill
        if progress > 0:
            fill_w = int(bar_w * progress)
            pygame.draw.rect(surface, (100, 200, 100),
                             (bx, by, fill_w, bar_h), border_radius=3)
