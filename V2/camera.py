"""
LiftSim V2 — Camera / Viewport System
=======================================
Scrollable camera that follows lifts or lets the user free-scroll
through the building cross-section.

State machine:
  FREE       → follow_lift_id == -1, user controls position
  FOLLOW     → follow_lift_id >= 0, camera tracks that lift's Y
  TRANSITION → Smooth lerp between positions (init or mode switch)

Supports:
  - Smooth lerp-based lift following
  - Keyboard scroll (UP/DOWN / W/S)
  - Mouse wheel scroll (auto-unfollows)
  - Scroll indicators (arrows when building extends beyond viewport)
  - World↔screen coordinate translation for click detection
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from lift_system import Lift


class Camera:
    """Manages vertical scroll offset for the building viewport.

    Attributes:
        y: Current camera Y offset (px). 0 = top of building.
        follow_lift_id: Lift index to follow, or -1 for free scroll.
        MIN_Y: Minimum scroll value (top of building).
        MAX_Y: Maximum scroll value (bottom of building visible).
        SCROLL_STEP: Pixels per keyboard scroll step.
    """

    SCROLL_STEP: int = 20
    LERP_SPEED: float = 6.0  # Lower = smoother, higher = snappier

    def __init__(self, max_y: float = 2000.0) -> None:
        self.y: float = 0.0
        self.follow_lift_id: int = -1
        self.MIN_Y: float = 0.0
        self.MAX_Y: float = max_y
        self._target_y: float = 0.0

    # ── Follow Control ─────────────────────────────────────────────────

    def follow_lift(self, lift_index: int) -> None:
        """Switch to follow mode for a specific lift."""
        self.follow_lift_id = lift_index

    def free_scroll(self) -> None:
        """Switch to free (manual) scroll mode."""
        self.follow_lift_id = -1

    def scroll(self, delta_px: float, screen_h: int, building_h: int) -> None:
        """Scroll manually by delta_px. Sets mode to FREE."""
        self.follow_lift_id = -1
        self._target_y = self.y + delta_px
        self._clamp_target(screen_h, building_h)
        self.y = self._target_y

    # ── Per-Frame Update ───────────────────────────────────────────────

    def update(self, dt: float, lifts: List[Lift], screen_h: int, lift_h: int) -> None:
        """Tick the camera — follows target lift if in FOLLOW mode.

        Lift-following targets the lift's Y so it's centred vertically.
        Uses smooth lerp to avoid jarring snaps.
        """
        if self.follow_lift_id >= 0 and self.follow_lift_id < len(lifts):
            lift = lifts[self.follow_lift_id]
            # Target: lift centred vertically on screen
            target_y = lift.current_y - screen_h / 2 + lift_h / 2
            target_y = max(self.MIN_Y, min(target_y, self.MAX_Y))

            # Smooth lerp toward target
            self.y += (target_y - self.y) * min(1.0, dt * self.LERP_SPEED)

            # Snap when close enough
            if abs(self.y - target_y) < 0.5:
                self.y = target_y

    # ── Coordinates Translation ────────────────────────────────────────

    def world_to_screen_y(self, world_y: float) -> float:
        """Convert a world Y coordinate to screen Y (subtract camera offset)."""
        return world_y - self.y

    def screen_to_world_y(self, screen_y: float) -> float:
        """Convert a screen Y coordinate to world Y (add camera offset)."""
        return screen_y + self.y

    def is_visible(self, world_y: float, screen_h: int, margin: float = 60.0) -> bool:
        """Check if a world Y coordinate is visible on screen."""
        screen_y = self.world_to_screen_y(world_y)
        return -margin <= screen_y <= screen_h + margin

    def is_rect_visible(self, world_y: float, height: float, screen_h: int,
                        margin: float = 60.0) -> bool:
        """Check if a vertical span (world_y to world_y+height) is visible."""
        top = self.world_to_screen_y(world_y)
        bottom = self.world_to_screen_y(world_y + height)
        return -(margin + height) <= top <= screen_h + margin  # noqa: SIM114

    # ── Internal ───────────────────────────────────────────────────────

    def _clamp_target(self, screen_h: int, building_h: int) -> None:
        """Clamp target Y within valid scroll range."""
        self._target_y = max(self.MIN_Y, min(self._target_y, self.MAX_Y))
