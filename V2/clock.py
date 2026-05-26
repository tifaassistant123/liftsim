"""
LiftSim V2 — WorldClock
=========================
A "world calendar" that tracks simulation time independently of real time.
Supports variable time scales (1x, 2x, 4x) via tick(dt).

Design:
  - 1 real second at 1x speed = 60 simulation seconds (1 sim-minute).
  - tick(dt) is called every frame with dt * speed_multiplier.
  - Properties expose sim_minute, sim_hour, day_of_week cleanly.
  - No direct pygame dependency — pure logic.
"""

from typing import Optional


class WorldClock:
    """Tracks simulated time with scale support.

    Attributes:
        total_seconds: Cumulative simulation seconds elapsed.
        time_scale: Current speed multiplier (1, 2, or 4).
        paused: Whether the clock is frozen.
    """

    def __init__(self, time_scale: int = 1) -> None:
        self.total_seconds: float = 0.0
        self._time_scale: int = time_scale
        self.paused: bool = False

    # ── Properties ──────────────────────────────────────────────────────

    @property
    def time_scale(self) -> int:
        return self._time_scale

    @time_scale.setter
    def time_scale(self, value: int) -> None:
        """Clamp to valid scale values."""
        self._time_scale = max(1, min(4, value))

    @property
    def sim_minute(self) -> int:
        """Current simulation minute (0–59)."""
        return int((self.total_seconds // 60) % 60)

    @property
    def sim_hour(self) -> int:
        """Current simulation hour (0–23)."""
        return int((self.total_seconds // 3600) % 24)

    @property
    def sim_day(self) -> int:
        """Number of full simulation days elapsed."""
        return int(self.total_seconds // (3600 * 24))

    @property
    def day_of_week(self) -> int:
        """Day of week (0=Mon … 6=Sun)."""
        return self.sim_day % 7

    @property
    def is_weekend(self) -> bool:
        return self.day_of_week >= 5

    # ── Core Logic ──────────────────────────────────────────────────────

    def tick(self, dt: float) -> None:
        """Advance simulation time by dt seconds at the current scale.

        Args:
            dt: Real delta-time in seconds (typically ~0.0167 at 60 FPS).
        """
        if self.paused:
            return
        # 1 real second = SIM_SECONDS_PER_REAL_SECOND sim seconds at 1x
        self.total_seconds += dt * 60.0 * self._time_scale

    def reset(self) -> None:
        """Reset the clock to zero."""
        self.total_seconds = 0.0
        self.paused = False

    # ── Time Representation ────────────────────────────────────────────

    DAY_NAMES: list[str] = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    def get_time_str(self) -> str:
        """Format current time as HH:MM."""
        return f"{self.sim_hour:02d}:{self.sim_minute:02d}"

    def get_day_name(self) -> str:
        """Get short day name (Mon–Sun)."""
        return self.DAY_NAMES[self.day_of_week]

    def get_full_time_str(self) -> str:
        """Format as 'Day HH:MM'."""
        return f"{self.get_day_name()} {self.get_time_str()}"

    def get_total_minutes(self) -> int:
        """Total simulation minutes elapsed today (0–1439)."""
        return self.sim_hour * 60 + self.sim_minute

    def __repr__(self) -> str:
        state = "⏸" if self.paused else "▶"
        return (
            f"<WorldClock {state} "
            f"{self.get_full_time_str()} "
            f"[Day {self.sim_day}] "
            f"{self._time_scale}x>"
        )
