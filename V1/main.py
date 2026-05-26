#!/usr/bin/env python3
"""
LiftSim 🛗 — Main Entry Point
Run: python main.py       (from LiftSim folder)
     run_liftsim.bat      (double-click anywhere)
"""

import sys
import os

# ── CRITICAL: Set up import path BEFORE any LiftSim imports ────────────
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Verify our modules are reachable
_sim_path = os.path.join(_PROJECT_ROOT, "simulation", "__init__.py")
_ren_path = os.path.join(_PROJECT_ROOT, "rendering", "__init__.py")
if not os.path.exists(_sim_path) or not os.path.exists(_ren_path):
    print("ERROR: LiftSim folder structure not found!")
    print(f"  Looking in: {_PROJECT_ROOT}")
    print(f"  simulation/__init__.py exists: {os.path.exists(_sim_path)}")
    print(f"  rendering/__init__.py exists: {os.path.exists(_ren_path)}")
    sys.exit(1)

# ── Now safe to import ─────────────────────────────────────────────────
import pygame
from simulation.sim_loop import init_simulation, update_simulation
from simulation.data_structures import (
    SIM_CLOCK, BUILDING_CONFIG, SIM_STATE, LIFTS, STATS, PEOPLE, EVENTS,
)
from rendering.renderer import Renderer, SCREEN_W, SCREEN_H

# ── Main ────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("LiftSim 🛗")
    clock = pygame.time.Clock()

    # Initialize simulation
    init_simulation()

    # Create renderer
    renderer = Renderer(screen)

    running = True
    while running:
        clock.tick(60)

        # ── Handle Input ──
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    SIM_CLOCK["paused"] = not SIM_CLOCK["paused"]

                elif event.key == pygame.K_1:
                    SIM_CLOCK["speed"] = 1
                elif event.key == pygame.K_2:
                    SIM_CLOCK["speed"] = 5
                elif event.key == pygame.K_3:
                    SIM_CLOCK["speed"] = 20
                elif event.key == pygame.K_4:
                    SIM_CLOCK["speed"] = 100

                elif event.key == pygame.K_UP:
                    from simulation.data_structures import create_lift
                    current = BUILDING_CONFIG["num_lifts"]
                    if current < 3:
                        new_lift = create_lift(current)
                        LIFTS[current] = new_lift
                        BUILDING_CONFIG["num_lifts"] = current + 1

                elif event.key == pygame.K_DOWN:
                    current = BUILDING_CONFIG["num_lifts"]
                    if current > 1:
                        del LIFTS[current - 1]
                        BUILDING_CONFIG["num_lifts"] = current - 1

                elif event.key == pygame.K_r:
                    PEOPLE.clear()
                    LIFTS.clear()
                    EVENTS["move_in_queue"].clear()
                    EVENTS["active_move"] = None
                    init_simulation()

        update_simulation()
        renderer.render()

        # FPS in corner
        fps_text = renderer.font_small.render(
            f"FPS: {clock.get_fps():.0f}", True, (100, 100, 110))
        screen.blit(fps_text, (SCREEN_W - 170, SCREEN_H - 22))

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
