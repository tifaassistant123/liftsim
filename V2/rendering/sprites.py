"""
LiftSim V2 — SpriteManager
===========================
Loads and manages 36x36 Pixel Lab character sprites.
Provides standing poses and walk animation frames.

Character mapping:
    WORKER   → working_adult_office_worker_1
    STUDENT  → student_student_1
    ELDER    → student_student_2 (placeholder until elder sprite generated)
    CHILD    → student_student_2 (placeholder)
    PET      → None (circle fallback)
    SHOPPER  → student_student_2 (placeholder)
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import pygame

from config import SimulationConfig
from entities import PersonType

# Path to sprites relative to project root
SPRITES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sprites")

# Map PersonType to sprite base name
TYPE_TO_SPRITE: Dict[PersonType, Optional[str]] = {
    PersonType.WORKER:   "working_adult_office_worker_1",
    PersonType.STUDENT:  "student_student_1",
    PersonType.ELDER:    "student_student_2",   # Placeholder
    PersonType.CHILD:    None,                    # No sprite yet
    PersonType.PET:      None,                    # No sprite
    PersonType.SHOPPER:  "student_student_2",     # Placeholder
}

# 8 compass directions matching pixel-lab export
DIRECTIONS: Tuple[str, ...] = (
    "west", "north-west", "north", "north-east",
    "east", "south-east", "south", "south-west",
)

# Walk frame count per direction
WALK_FRAMES: int = 6
WALK_CYCLE_DURATION: float = 0.8  # seconds for full cycle


class SpriteManager:
    """Singleton sprite cache — loads all sprites on first use.

    Access:
        sm = SpriteManager.get_instance()
        standing = sm.get_standing(PersonType.WORKER, "south")
        walk_01 = sm.get_walk(PersonType.WORKER, "south", 1)
    """

    _instance: Optional[SpriteManager] = None

    def __init__(self) -> None:
        self._standing: Dict[str, pygame.Surface] = {}
        self._walk: Dict[str, List[pygame.Surface]] = {}
        self._load_all()

    # ── Singleton ───────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> SpriteManager:
        if cls._instance is None:
            cls._instance = SpriteManager()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Force reload on next access (e.g. after adding new sprites)."""
        cls._instance = None

    # ── Loading ─────────────────────────────────────────────────────────

    def _load_all(self) -> None:
        """Iterate over sprite directory, load all PNGs into cache."""
        if not os.path.isdir(SPRITES_DIR):
            print(f"[WARN] Sprite dir not found: {SPRITES_DIR}")
            return

        for fname in os.listdir(SPRITES_DIR):
            if not fname.endswith(".png"):
                continue

            path = os.path.join(SPRITES_DIR, fname)
            try:
                surf = pygame.image.load(path).convert_alpha()
            except Exception as e:
                print(f"[ERR] Failed to load {fname}: {e}")
                continue

            # Strip .png, parse name
            name = fname[:-4]
            parts = name.split("_")

            if "walk" in parts:
                # e.g. student_student_1_walk_south_00
                # Find walk index, the frame number is last
                walk_idx = parts.index("walk")
                base = "_".join(parts[:walk_idx])   # e.g. student_student_1
                # Direction is after "walk"
                dir_start = walk_idx + 1
                # Direction could be two words (north-east) or one
                # Parse: everything between walk_idx+1 and the frame number
                dir_parts = parts[dir_start:]
                frame_str = dir_parts[-1]
                dir_name = "_".join(dir_parts[:-1])  # e.g. "south-east"

                key = f"{base}_{dir_name}"
                if key not in self._walk:
                    self._walk[key] = [None] * WALK_FRAMES

                try:
                    frame_num = int(frame_str)
                    if 0 <= frame_num < WALK_FRAMES:
                        self._walk[key][frame_num] = surf
                except ValueError:
                    pass
            else:
                # Standing sprite: base_direction
                # Direction is the last 1-2 segments
                if parts[-1] in DIRECTIONS:
                    base = "_".join(parts[:-1])
                    dir_name = parts[-1]
                elif "_".join(parts[-2:]) in DIRECTIONS:
                    base = "_".join(parts[:-2])
                    dir_name = "_".join(parts[-2:])  # e.g. north-east
                else:
                    # Fallback: treat entire name as key
                    base = name
                    dir_name = "south"

                key = f"{base}_{dir_name}"
                self._standing[key] = surf

    # ── Query ───────────────────────────────────────────────────────────

    def get_standing(self, person_type: PersonType,
                     direction: str = "south") -> Optional[pygame.Surface]:
        """Get standing sprite for a character type and facing direction."""
        base = TYPE_TO_SPRITE.get(person_type)
        if base is None:
            return None
        key = f"{base}_{direction}"
        return self._standing.get(key)

    def get_walk(self, person_type: PersonType,
                 direction: str = "south",
                 frame: int = 0) -> Optional[pygame.Surface]:
        """Get a walk animation frame for a character type and direction."""
        base = TYPE_TO_SPRITE.get(person_type)
        if base is None:
            return None
        key = f"{base}_{direction}"
        frames = self._walk.get(key)
        if frames and frame < len(frames):
            return frames[frame]
        return None

    def has_sprites(self, person_type: PersonType) -> bool:
        """Check if character has sprites loaded."""
        return TYPE_TO_SPRITE.get(person_type) is not None

    # ── Stats ───────────────────────────────────────────────────────────

    def stats(self) -> str:
        standing_count = len(self._standing)
        walk_frames_count = sum(len(v) for v in self._walk.values())
        return f"[OK] {standing_count} standing + {walk_frames_count} walk frames"

    def get_facing_direction(self, dx: float, dy: float) -> str:
        """Convert movement vector (dx, dy) to compass direction string.

        Args:
            dx: Horizontal movement (-1 to 1)
            dy: Vertical movement (-1 to 1, screen coords where down = +)

        Returns:
            One of 8 compass directions.
        """
        if abs(dx) < 0.001 and abs(dy) < 0.001:
            return "south"  # Default facing

        # Atan2 gives radians CCW from east
        import math
        angle = math.degrees(math.atan2(dy, dx))
        # Convert: N=0, E=90, S=180, W=270
        # But in screen coords, down = +y, so +y is S
        # atan2(dy, dx) where dy=down gives angle from east:
        # dy=+1 (south), dx=0 → atan2(1, 0) = 90°
        # We want: east=90°, south-east=135°, south=180°, south-west=225°
        # west=270°, north-west=315°, north=0°, north-east=45°

        if angle < 0:
            angle += 360

        # Map to 8 directions
        buckets = [
            (22.5, "east"), (67.5, "south-east"), (112.5, "south"),
            (157.5, "south-west"), (202.5, "west"), (247.5, "north-west"),
            (292.5, "north"), (337.5, "north-east"),
        ]
        for threshold, direction in buckets:
            if angle < threshold:
                return direction
        return "east"


# ══════════════════════════════════════════════════════════════════════════
# LiftSpriteLoader: Lift Door Animation Frames
# ══════════════════════════════════════════════════════════════════════════

LIFT_SPRITES_DIR = os.path.join(SPRITES_DIR, "lift")


class LiftSpriteLoader:
    """Singleton — loads and caches lift door animation sprites.

    Frames are numbered 1–8 where:
        Frame 1 = doors fully closed
        Frame 8 = doors fully open (widest gap)

    Access:
        lsl = LiftSpriteLoader.get_instance()
        frame = lsl.get_frame(0)   # closed
        frame = lsl.get_frame(7)   # open
    """

    _instance: Optional[LiftSpriteLoader] = None

    def __init__(self) -> None:
        self._frames: List[Optional[pygame.Surface]] = []
        self._load_all()

    @classmethod
    def get_instance(cls) -> LiftSpriteLoader:
        if cls._instance is None:
            cls._instance = LiftSpriteLoader()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def _load_all(self) -> None:
        """Load frames lift_01_0001.png through lift_01_0008.png."""
        if not os.path.isdir(LIFT_SPRITES_DIR):
            print(f"[WARN] Lift sprite dir not found: {LIFT_SPRITES_DIR}")
            return

        for i in range(1, 9):
            fname = f"lift_01_{i:04d}.png"
            path = os.path.join(LIFT_SPRITES_DIR, fname)
            try:
                surf = pygame.image.load(path)
                # convert_alpha may fail if display not initialized yet
                try:
                    surf = surf.convert_alpha()
                except pygame.error:
                    pass  # Non-optimized but functional
                self._frames.append(surf)
            except Exception as e:
                print(f"[ERR] Failed to load lift sprite {fname}: {e}")
                self._frames.append(None)

    def get_frame(self, index: int) -> Optional[pygame.Surface]:
        """Get frame by 0-based index (0=closed, 7=fully open)."""
        if 0 <= index < len(self._frames):
            return self._frames[index]
        return None

    @property
    def frame_count(self) -> int:
        return len(self._frames)

    def stats(self) -> str:
        loaded = sum(1 for f in self._frames if f is not None)
        return f"[OK] {loaded}/{len(self._frames)} lift door frames loaded"
