"""
LiftSim V2 — UI Widgets
========================
Reusable, decoupled UI components: Button, Slider, Label.
All drawing uses `pygame.draw.rect(border_radius=...)` for modern rounded corners.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from ui.theme import Theme


# ── Label ────────────────────────────────────────────────────────────────

class Label:
    """Static text display."""

    def __init__(self, text: str, theme: Theme, font_size: Optional[int] = None,
                 colour: Optional[tuple] = None) -> None:
        self.text = text
        self.theme = theme
        self.font_size = font_size or theme.FONT_SIZE_BODY
        self.colour = colour or theme.text_primary
        self._surface = None
        self._render()

    def _render(self) -> None:
        font = self.theme.get_font(self.font_size)
        self._surface = font.render(self.text, True, self.colour)

    def set_text(self, text: str) -> None:
        self.text = text
        self._render()

    @property
    def width(self) -> int:
        return self._surface.get_width() if self._surface else 0

    @property
    def height(self) -> int:
        return self._surface.get_height() if self._surface else 0

    def draw(self, surface: pygame.Surface, x: int, y: int) -> None:
        if self._surface:
            surface.blit(self._surface, (x, y))


# ── Button ───────────────────────────────────────────────────────────────

class Button:
    """Clickable button with hover feedback.

    Args:
        rect: Bounding rectangle.
        text: Button label.
        on_click: Callback when clicked.
        theme: Theme reference.
        is_start: If True, uses green start-button colours.
    """

    def __init__(self, rect: pygame.Rect, text: str,
                 on_click: Callable[[], None],
                 theme: Theme, is_start: bool = False) -> None:
        self.rect = rect
        self.text = text
        self.on_click = on_click
        self.theme = theme
        self.is_start = is_start
        self.hovered = False
        self._label = Label(text, theme, theme.FONT_SIZE_BODY, theme.button_text)

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process a pygame event. Returns True if this widget consumed it."""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        bg = self.theme.start_bg if self.is_start else self.theme.button_bg
        if self.hovered:
            bg = self.theme.start_hover if self.is_start else self.theme.button_hover

        # Rounded rectangle
        pygame.draw.rect(surface, bg, self.rect, border_radius=8)
        pygame.draw.rect(surface, self.theme.panel_border, self.rect,
                         width=2, border_radius=8)

        # Centred text
        lx = self.rect.centerx - self._label.width // 2
        ly = self.rect.centery - self._label.height // 2
        self._label.draw(surface, lx, ly)


# ── Slider ───────────────────────────────────────────────────────────────

class Slider:
    """Draggable horizontal slider with label and live value display.

    Args:
        rect: Full bounding box (label + track + thumb).
        min_val: Minimum value (leftmost).
        max_val: Maximum value (rightmost).
        default: Starting value.
        step: Snap increment (0 = smooth).
        label: Display label text.
        on_change: Called with new value when user drags.
        display_decimals: How many decimals to show (0 = int display).
        suffix: Suffix string (e.g. "x", "s", "").
        theme: Theme reference.
    """

    def __init__(self, rect: pygame.Rect, min_val: float, max_val: float,
                 default: float, step: float, label: str,
                 on_change: Callable[[float], None],
                 theme: Theme,
                 display_decimals: int = 0, suffix: str = "") -> None:
        self.rect = rect
        self.min_val = min_val
        self.max_val = max_val
        self.value = default
        self.step = step
        self.label = label
        self.on_change = on_change
        self.display_decimals = display_decimals
        self.suffix = suffix
        self.theme = theme

        self.dragging = False

        # Track geometry
        track_y = rect.y + theme.WIDGET_GAP + 6
        self.track_rect = pygame.Rect(rect.x + 4, track_y,
                                      rect.width - 8, 6)
        self._thumb_radius = 8
        self._thumb_y = track_y + 3

        self._label_widget = Label(label, theme, theme.FONT_SIZE_SMALL,
                                   theme.text_secondary)

    @property
    def _thumb_x(self) -> int:
        """X position of the thumb based on current value."""
        frac = (self.value - self.min_val) / max(self.max_val - self.min_val, 1)
        return int(self.track_rect.x + frac * self.track_rect.width)

    def _value_from_x(self, x: int) -> float:
        """Convert a pixel x to a value."""
        frac = (x - self.track_rect.x) / max(self.track_rect.width, 1)
        frac = max(0.0, min(1.0, frac))
        raw = self.min_val + frac * (self.max_val - self.min_val)
        if self.step > 0:
            raw = round(raw / self.step) * self.step
        return max(self.min_val, min(self.max_val, raw))

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.value = self._value_from_x(event.pos[0])
                self.on_change(self.value)
                return True

        if event.type == pygame.MOUSEMOTION and self.dragging:
            self.value = self._value_from_x(event.pos[0])
            self.on_change(self.value)
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1 and self.dragging:
            self.dragging = False
            return True

        return False

    def draw(self, surface: pygame.Surface) -> None:
        # Label
        self._label_widget.draw(surface, self.rect.x, self.rect.y)

        # Value text on the right
        val_str = f"{self.value:.{self.display_decimals}f}{self.suffix}"
        val_widget = Label(val_str, self.theme, self.theme.FONT_SIZE_SMALL,
                           self.theme.text_accent)
        vx = self.rect.right - val_widget.width
        val_widget.draw(surface, vx, self.rect.y)

        # Track background
        pygame.draw.rect(surface, self.theme.slider_track,
                         self.track_rect, border_radius=3)

        # Track fill
        fill_w = self._thumb_x - self.track_rect.x
        if fill_w > 2:
            fill_rect = pygame.Rect(self.track_rect.x, self.track_rect.y,
                                    fill_w, self.track_rect.height)
            pygame.draw.rect(surface, self.theme.slider_fill,
                             fill_rect, border_radius=3)

        # Thumb (circle)
        pygame.draw.circle(surface, self.theme.slider_thumb,
                           (self._thumb_x, self._thumb_y),
                           self._thumb_radius)

        # Glow when dragging
        if self.dragging:
            pygame.draw.circle(surface, (180, 220, 255, 80),
                               (self._thumb_x, self._thumb_y),
                               self._thumb_radius + 4, width=2)
