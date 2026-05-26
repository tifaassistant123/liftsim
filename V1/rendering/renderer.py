"""
LiftSim — Pixel-style Renderer
================================
Draws the building cross-section view with pygame-ce.
Pixel art style using simple rectangles, dots, and symbols.
"""

import pygame
from simulation.data_structures import (
    SIM_CLOCK, PEOPLE, LIFTS, STATS, BUILDING_CONFIG, SIM_STATE, EVENTS,
    Location, LiftDirection, FlatSize,
)

# ── Colors (Pixel palette) ──────────────────────────────────────────────

# Building structure
COLOR_SKY_DAY       = (135, 206, 235)  # Light sky blue
COLOR_SKY_NIGHT     = (20, 24, 50)     # Dark navy
COLOR_BUILDING      = (60, 60, 65)     # Building exterior
COLOR_BUILDING_INNER = (45, 45, 50)    # Inside walls
COLOR_WALL          = (80, 78, 82)     # Floor/ceiling separators
COLOR_FLOOR_LINE    = (55, 55, 60)     # Floor boundary lines
COLOR_LOBBY         = (180, 160, 140)  # Ground floor lobby
COLOR_DOOR          = (160, 130, 80)   # Flat door (closed)
COLOR_DOOR_OPEN     = (200, 180, 120)  # Flat door (open)
COLOR_WINDOW_LIT    = (255, 220, 100)  # Window with light on
COLOR_WINDOW_UNLIT  = (40, 40, 60)     # Window dark

# Lift
COLOR_LIFT_SHAFT    = (35, 35, 40)     # Shaft background
COLOR_LIFT_CAB      = (180, 70, 70)    # Lift cabin (red accent)
COLOR_LIFT_DOOR     = (200, 100, 100)  # Lift door
COLOR_LIFT_DOOR_OPEN = (220, 140, 140)

# People
COLOR_PERSON_WORKER  = (100, 180, 255)  # Blue
COLOR_PERSON_STUDENT = (100, 255, 150)  # Green
COLOR_PERSON_RETIREE = (255, 200, 100)  # Orange
COLOR_PERSON_KID     = (255, 100, 200)  # Pink
COLOR_PERSON_PET     = (180, 140, 100)  # Brown

# UI
COLOR_UI_BG         = (15, 15, 20)
COLOR_UI_TEXT       = (200, 200, 210)
COLOR_UI_ACCENT     = (220, 120, 100)  # Warm red accent
COLOR_UI_GREEN      = (100, 220, 150)
COLOR_UI_YELLOW     = (220, 220, 100)

PERSON_COLORS = {
    "WORKER":  COLOR_PERSON_WORKER,
    "STUDENT": COLOR_PERSON_STUDENT,
    "RETIREE": COLOR_PERSON_RETIREE,
    "KID":     COLOR_PERSON_KID,
    "PET":     COLOR_PERSON_PET,
    "BABY":    COLOR_PERSON_KID,
}

FLAT_COLORS = {
    FlatSize.STUDIO:  (100, 90, 110),
    FlatSize.ONE_BR:  (80, 90, 105),
    FlatSize.TWO_BR:  (75, 85, 100),
    FlatSize.THREE_BR: (70, 80, 95),
}

# ── Layout ──────────────────────────────────────────────────────────────

SCREEN_W = 900
SCREEN_H = 700

MARGIN_LEFT = 80
MARGIN_TOP = 30
MARGIN_RIGHT = 180  # Space for UI panel
BUILDING_W = SCREEN_W - MARGIN_LEFT - MARGIN_RIGHT
BUILDING_H = SCREEN_H - MARGIN_TOP - 40

# ── Renderer ────────────────────────────────────────────────────────────

class Renderer:
    def __init__(self, screen):
        self.screen = screen
        self.font_small = pygame.Font(None, 14)
        self.font_med = pygame.Font(None, 18)
        self.font_large = pygame.Font(None, 24)
        self.font_title = pygame.Font(None, 32)
        self.clock_font = pygame.Font(None, 48)
        self.pixel_font = pygame.Font(None, 16)

    def render(self):
        """Main render call — draw everything."""
        now = SIM_CLOCK["game_minute"]

        # Determine sky color (day/night cycle)
        h = (now // 60) % 24
        if 6 <= h < 18:
            sky = COLOR_SKY_DAY
            self.daytime = "day"
        else:
            sky = COLOR_SKY_NIGHT
            self.daytime = "night"

        # Calculate dynamic layout
        num_floors = BUILDING_CONFIG["num_floors"]
        floor_h = min(50, (BUILDING_H - 20) // max(num_floors, 1))
        building_h = floor_h * (num_floors + 1)  # +1 for ground

        self.building_rect = pygame.Rect(
            MARGIN_LEFT, MARGIN_TOP + BUILDING_H - building_h,
            BUILDING_W, building_h
        )

        # ── Draw sky background ──
        self.screen.fill(sky)

        # ── Draw building ──
        bx, by = self.building_rect.topleft
        bw, bh = self.building_rect.size

        # Building exterior
        pygame.draw.rect(self.screen, COLOR_BUILDING, self.building_rect)
        pygame.draw.rect(self.screen, COLOR_BUILDING_INNER,
                         (bx + 10, by + 10, bw - 20, bh - 20))

        # ── Draw floors ──
        num_lifts = BUILDING_CONFIG["num_lifts"]
        lift_shaft_w = 40
        total_lift_w = lift_shaft_w * num_lifts + 10 * (num_lifts - 1)
        flats_w = bw - 20 - total_lift_w - 20  # Space for flats on each side

        for floor_idx in range(num_floors):
            fy = by + bh - (floor_idx + 1) * floor_h

            # Floor separator line
            pygame.draw.line(self.screen, COLOR_FLOOR_LINE,
                             (bx + 10, fy), (bx + bw - 10, fy), 2)

            # Floor label
            floor_label = f"{'G' if floor_idx == 0 else floor_idx}"
            label_surf = self.font_small.render(floor_label, True, COLOR_UI_TEXT)
            self.screen.blit(label_surf, (bx - 25, fy + floor_h // 2 - 6))

            if floor_idx == 0:
                # Ground floor — lobby
                lobby_rect = pygame.Rect(bx + 15, fy + 4, bw - 30, floor_h - 8)
                pygame.draw.rect(self.screen, COLOR_LOBBY, lobby_rect)
                # Lobby text
                lobby_text = self.font_small.render("🏢 LOBBY", True, (60, 50, 40))
                self.screen.blit(lobby_text, (bx + 30, fy + floor_h // 2 - 7))

                # Lift doors on ground
                for li in range(num_lifts):
                    lx = bx + bw // 2 - total_lift_w // 2 + li * (lift_shaft_w + 10)
                    lift = LIFTS.get(li)
                    is_here = lift and lift["current_floor"] == 0
                    door_color = COLOR_LIFT_DOOR_OPEN if (is_here and lift["doors_open"]) else COLOR_LIFT_DOOR
                    pygame.draw.rect(self.screen, door_color,
                                     (lx, fy + 6, lift_shaft_w, floor_h - 16))

                    # Lift label
                    lid_label = self.font_small.render(f"L{li+1}", True, (255, 255, 255))
                    self.screen.blit(lid_label, (lx + 5, fy + floor_h // 2 - 14))

                # Lobby decorations
                door_mat = self.font_small.render("🚪", True, (80, 70, 50))
                self.screen.blit(door_mat, (bx + bw - 50, fy + 8))

            else:
                # Residential floors
                flats = SIM_STATE.get("building", {}).get(floor_idx, [])
                if not flats:
                    flats = []

                # Split flats left and right of lift shaft
                left_flats = flats[:len(flats)//2] if len(flats) > 1 else []
                right_flats = flats[len(flats)//2:] if flats else flats

                flat_h = floor_h - 8

                # Left flats
                left_w = (bw - 20 - total_lift_w - 20) // max(1, len(left_flats))
                for fi, flat in enumerate(left_flats):
                    fx = bx + 15 + fi * left_w
                    self._draw_flat(fx, fy + 4, left_w - 2, flat_h, flat)

                # Right flats
                right_w = (bw - 20 - total_lift_w - 20) // max(1, len(right_flats))
                for fi, flat in enumerate(right_flats):
                    fx = bx + 15 + (bw - 20 - total_lift_w - 20) + total_lift_w + 20 + fi * right_w
                    self._draw_flat(fx, fy + 4, right_w - 2, flat_h, flat)

                # ── Lift shaft ──
                for li in range(num_lifts):
                    lx = bx + bw // 2 - total_lift_w // 2 + li * (lift_shaft_w + 10)

                    # Shaft background (drawn once per floor, full height)
                    shaft_rect = pygame.Rect(lx, by + 10, lift_shaft_w, bh - 20)
                    pygame.draw.rect(self.screen, COLOR_LIFT_SHAFT, shaft_rect)

                    # Shaft divisions at each floor level
                    pygame.draw.line(self.screen, (30, 30, 35),
                                     (lx, fy), (lx + lift_shaft_w, fy), 1)

                    # Shaft rail lines
                    pygame.draw.line(self.screen, (50, 50, 60),
                                     (lx + 2, fy), (lx + 2, fy + floor_h), 1)
                    pygame.draw.line(self.screen, (50, 50, 60),
                                     (lx + lift_shaft_w - 2, fy),
                                     (lx + lift_shaft_w - 2, fy + floor_h), 1)

        # ── Draw lift cabs (interpolated between floors) ──
        for li in range(num_lifts):
            lift = LIFTS.get(li)
            if not lift:
                continue

            lx = bx + bw // 2 - total_lift_w // 2 + li * (lift_shaft_w + 10)

            # Ground floor y-position
            ground_fy = by + bh - (0 + 1) * floor_h
            # Current floor top y-position
            current_fy = by + bh - (lift["current_floor"] + 1) * floor_h

            # Calculate interpolated Y position
            direction = lift["direction"].value  # 1=UP, -1=DOWN, 0=IDLE
            progress = lift["progress"]

            if direction == 0 or abs(progress) < 0.001:
                # Not moving — cab sits at current floor
                cab_y = current_fy + 4
            else:
                # Moving — interpolate: progress 0→1 moves one floor
                cab_y = current_fy + 4 - direction * floor_h * progress

            cab_h = floor_h - 8
            cab_color = COLOR_LIFT_DOOR_OPEN if lift["doors_open"] else COLOR_LIFT_CAB

            # Clamp to building bounds
            cab_y = max(by + 14, min(by + bh - cab_h - 14, cab_y))

            pygame.draw.rect(self.screen, cab_color,
                             (lx + 2, int(cab_y), lift_shaft_w - 4, int(cab_h)))

            # Passengers inside
            if lift["passengers"]:
                for pi, pid in enumerate(lift["passengers"][:3]):
                    p = PEOPLE.get(pid)
                    if p:
                        px = lx + 5 + pi * 10
                        ptype = p["type"].name
                        pc = PERSON_COLORS.get(ptype, (255, 255, 255))
                        pygame.draw.circle(self.screen, pc,
                                           (px + 5, int(cab_y + cab_h - 8)), 3)

        # ── Draw UI Panel ──
        self._draw_ui()

        # ── Draw time overlay ──
        self._draw_time_overlay()

    def _draw_flat(self, x, y, w, h, flat):
        """Draw a single flat with door, window, and occupant dots."""
        # Flat interior
        size = flat["size"]
        fc = FLAT_COLORS.get(size, (70, 80, 95))
        pygame.draw.rect(self.screen, fc, (x, y, w, h), border_radius=2)

        # Flat border
        pygame.draw.rect(self.screen, COLOR_WALL, (x, y, w, h), 1)

        # Door
        door_w = min(16, w // 3)
        door_x = x + (w - door_w) // 2
        door_y = y + h - 18
        is_occupied = len(flat["occupants"]) > 0
        door_c = COLOR_DOOR_OPEN if is_occupied else COLOR_DOOR
        pygame.draw.rect(self.screen, door_c,
                         (door_x, door_y, door_w, 16), border_radius=2)
        # Door knob
        pygame.draw.circle(self.screen, (200, 180, 100),
                           (door_x + door_w - 4, door_y + 8), 2)

        # Window (lit if occupied and nighttime)
        is_lit = is_occupied and self.daytime == "night"
        win_c = COLOR_WINDOW_LIT if is_lit else COLOR_WINDOW_UNLIT
        pygame.draw.rect(self.screen, win_c,
                         (x + 4, y + 4, w - 8, 6), border_radius=1)

        # Occupant dots
        occupants = flat["occupants"]
        if occupants:
            dot_spacing = min(10, w // max(len(occupants), 1))
            for oi, pid in enumerate(occupants):
                p = PEOPLE.get(pid)
                if p and p["location"] == Location.HOME:
                    px = x + 4 + oi * dot_spacing
                    py = y + h - 6
                    ptype = p["type"].name
                    pc = PERSON_COLORS.get(ptype, (255, 255, 255))
                    pygame.draw.circle(self.screen, pc, (px, py), 3)

        # Flat label
        label = flat["id"]
        label_s = self.font_small.render(label, True, (160, 160, 170))
        self.screen.blit(label_s, (x + 3, y + 14))

        # Occupancy indicator
        occ_text = f"{len(occupants)}/{flat['max_capacity']}"
        occ_s = self.font_small.render(occ_text, True, (130, 130, 140))
        self.screen.blit(occ_s, (x + w - len(occ_text) * 7 - 3, y + 14))

    def _draw_time_overlay(self):
        """Draw large time display at top center."""
        now = SIM_CLOCK["game_minute"]
        h = (now // 60) % 24
        m = now % 60
        time_str = f"{h:02d}:{m:02d}"

        day_name = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
            SIM_CLOCK["day_of_week"]]
        day_str = f"Day {SIM_CLOCK['game_days_elapsed']} | {day_name}"

        # Semi-transparent bar at top
        bar = pygame.Surface((self.screen.get_width(), 55), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 120))
        self.screen.blit(bar, (0, 0))

        # Time
        time_surf = self.clock_font.render(time_str, True, (255, 255, 255))
        self.screen.blit(time_surf, (20, 5))

        # Day
        day_surf = self.font_med.render(day_str, True, COLOR_UI_TEXT)
        self.screen.blit(day_surf, (20, 42))

        # Paused indicator
        if SIM_CLOCK["paused"]:
            pause_surf = self.font_large.render("⏸ PAUSED", True, COLOR_UI_YELLOW)
            self.screen.blit(pause_surf, (self.screen.get_width() // 2 - 60, 15))
        else:
            # Speed info
            speed_str = f"{SIM_CLOCK['speed']}x"
            speed_surf = self.font_med.render(speed_str, True, COLOR_UI_GREEN)
            self.screen.blit(speed_surf, (170, 42))

    def _draw_ui(self):
        """Draw the right-side stats panel."""
        px = self.screen.get_width() - MARGIN_RIGHT + 10
        py = MARGIN_TOP + 10

        # Panel background
        panel = pygame.Surface((MARGIN_RIGHT - 10, self.screen.get_height() - 20))
        panel.fill(COLOR_UI_BG)
        panel.set_alpha(200)
        self.screen.blit(panel, (px - 5, py))

        # Title
        title = self.font_title.render("📊 STATS", True, COLOR_UI_ACCENT)
        self.screen.blit(title, (px, py))
        py += 35

        # Summary stats
        stats_lines = [
            (f"👥 Pop: {STATS['total_residents']}", COLOR_UI_TEXT),
            (f"🏘️ Families: {STATS['total_families']}", COLOR_UI_TEXT),
            (f"🛗 Lifts: {BUILDING_CONFIG['num_lifts']}", COLOR_UI_TEXT),
            (f"🏢 Floors: {BUILDING_CONFIG['num_floors']}", COLOR_UI_TEXT),
        ]
        for text, color in stats_lines:
            surf = self.font_med.render(text, True, color)
            self.screen.blit(surf, (px, py))
            py += 22

        py += 10
        sep = self.font_small.render("─" * 12, True, (80, 80, 90))
        self.screen.blit(sep, (px, py))
        py += 15

        # Lift status
        lift_title = self.font_med.render("🛗 Lifts", True, COLOR_UI_ACCENT)
        self.screen.blit(lift_title, (px, py))
        py += 22

        for lid, lift in LIFTS.items():
            floor_str = f"F{lift['current_floor']}"
            dir_str = {1: "⬆", -1: "⬇", 0: "⏸"}.get(lift["direction"].value, "⏸")
            pass_str = f"👥{len(lift['passengers'])}"
            line = f"L{lift['id']+1}: {dir_str} {floor_str} {pass_str}"
            surf = self.font_small.render(line, True, COLOR_UI_TEXT)
            self.screen.blit(surf, (px, py))
            py += 18

        py += 10
        self.screen.blit(sep, (px, py))
        py += 15

        # Controls
        ctrl_title = self.font_med.render("⌨ Controls", True, COLOR_UI_ACCENT)
        self.screen.blit(ctrl_title, (px, py))
        py += 22

        controls = [
            "SPACE: Pause/Resume",
            "1/2/3: Speed 1x/5x/20x",
            "↑↓: Lift count (1-3)",
            "R: Reset building",
        ]
        for ctrl in controls:
            surf = self.font_small.render(ctrl, True, (150, 150, 160))
            self.screen.blit(surf, (px, py))
            py += 16

        # Event queue
        if EVENTS["move_in_queue"]:
            py += 10
            self.screen.blit(sep, (px, py))
            py += 15
            ev_title = self.font_small.render("📦 Pending Moves:", True, COLOR_UI_YELLOW)
            self.screen.blit(ev_title, (px, py))
            py += 18
            for ev in EVENTS["move_in_queue"][:3]:
                if ev["status"] == "pending":
                    ev_text = f"  ▶ In: {ev['flat_id']} ({ev['family_size']}p)"
                    surf = self.font_small.render(ev_text, True, COLOR_UI_GREEN)
                    self.screen.blit(surf, (px, py))
                    py += 16
