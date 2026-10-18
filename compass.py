# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame-ce"]
# ///
"""Attitude indicator, directional gyro and turn coordinator driven by the MacBook's IMU.

Run:  make run   (builds libimu.dylib, then: uv run compass.py)

Controls (Shift = 10x):
    DG HDG knob   click its arrows (hold to repeat), scroll over it, or Left / Right
    DG BUG knob   click its arrows (hold to repeat), scroll over it, or [ / ]
    C recalibrate gyro bias, Q quit
"""

import math
import sys
import time

import pygame

import sensors
from art import BOX, CARD_R, KNOB_R
from attitude_indicator import AttitudeIndicator
from directional_gyro import DirectionalGyro
from turn_coordinator import TurnCoordinator

GAP = 28
W, H = 3 * BOX + 4 * GAP, 700
CENTERS = [(GAP + BOX // 2 + i * (BOX + GAP), 150 + BOX // 2) for i in range(3)]
AI_CENTER, DG_CENTER, TC_CENTER = CENTERS
REPEAT_DELAY, REPEAT_EVERY = 0.4, 0.06  # s, holding a knob arrow

BG = (18, 20, 24)
FG = (235, 235, 235)
DIM = (130, 135, 145)
ACCENT = (255, 165, 0)
GOOD, WARN, BAD = (80, 200, 120), (240, 190, 60), (230, 80, 70)
POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def signed(value, places):
    """+1.5 / -2.0 / +0.0, never -0.0"""
    return f"{round(value, places) + 0.0:+.{places}f}"


def text(screen, font, s, color, center):
    surf = font.render(s, True, color)
    screen.blit(surf, surf.get_rect(center=center))


def draw_readouts(screen, fonts, ai, dg, tc):
    hdg = dg.indicated
    for center, big, small in (
        (AI_CENTER, f"{signed(ai.pitch, 0)}° / {signed(ai.roll, 0)}°",
         f"pitch {signed(ai.pitch, 1)}°   ·   roll {signed(ai.roll, 1)}°"),
        (DG_CENTER, f"{round(hdg) % 360:03d}°",
         f"{POINTS[int((hdg + 22.5) // 45) % 8]}   ·   bug {round(dg.bug) % 360:03d}°"),
        (TC_CENTER, f"{signed(tc.turn_rate, 1)}°/s",
         f"turn rate   ·   ball {signed(tc.ball, 1)}°"),
    ):
        text(screen, fonts["readout"], big, FG, (center[0], 62))
        text(screen, fonts["small"], small, DIM, (center[0], 112))


def draw_calibrating(screen, fonts, imu):
    progress = min(1.0, (time.monotonic() - imu.cal_started) / sensors.CAL_SECS)
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for center in CENTERS:
        pygame.draw.circle(shade, (0, 0, 0, 200), center, CARD_R + 4)
    screen.blit(shade, (0, 0))
    for center in CENTERS:
        ring = pygame.Rect(0, 0, 2 * CARD_R - 40, 2 * CARD_R - 40)
        ring.center = center
        pygame.draw.arc(screen, ACCENT, ring, math.pi / 2 - progress * 2 * math.pi, math.pi / 2, 8)
        text(screen, fonts["title"], "Hold still", FG, (center[0], center[1] - 18))
        text(screen, fonts["small"], "measuring gyro bias", FG, (center[0], center[1] + 22))


def draw_status(screen, fonts, imu, card_set_at):
    since = time.monotonic() - card_set_at
    if imu.cal_warning:
        color, status = BAD, "Moved during calibration: press C and hold still"
    else:
        color = GOOD if since < 300 else WARN if since < 900 else BAD
        status = f"heading set {int(since // 60)}m {int(since % 60):02d}s ago   ·   IMU {imu.temp:.1f}°C"
    surf = fonts["small"].render(status, True, FG)
    rect = surf.get_rect(center=(W // 2 + 10, H - 100))
    pygame.draw.circle(screen, color, (rect.left - 18, rect.centery), 7)
    screen.blit(surf, rect)
    hints = ("DG knobs: click the arrows (hold to repeat) or scroll · keys Left/Right heading, [ ] bug (Shift = 10°)",
             "C recalibrate   ·   Q quit")
    for i, line in enumerate(hints):
        text(screen, fonts["hint"], line, DIM, (W // 2, H - 52 + i * 24))


def main():
    screenshot = sys.argv[sys.argv.index("--screenshot") + 1] if "--screenshot" in sys.argv else None

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Attitude · Heading · Turn")
    fonts = {"readout": pygame.font.Font(None, 84), "title": pygame.font.Font(None, 44),
             "small": pygame.font.Font(None, 26), "hint": pygame.font.Font(None, 21)}
    ai, dg, tc = AttitudeIndicator(), DirectionalGyro(), TurnCoordinator()
    imu = sensors.Imu()
    card_set_at = time.monotonic()
    clock = pygame.time.Clock()

    def turn_card(degrees):
        nonlocal card_set_at
        dg.turn_card(degrees)
        card_set_at = time.monotonic()

    knobs = [((DG_CENTER[0] + dx, DG_CENTER[1] + dy), turn)
             for (dx, dy), turn in ((DirectionalGyro.KNOBS["card"], turn_card), (DirectionalGyro.KNOBS["bug"], dg.turn_bug))]
    keys = {pygame.K_LEFT: (turn_card, -1), pygame.K_RIGHT: (turn_card, 1),
            pygame.K_LEFTBRACKET: (dg.turn_bug, -1), pygame.K_RIGHTBRACKET: (dg.turn_bug, 1)}

    def knob_under(pos):
        for at, turn in knobs:
            if math.dist(pos, at) <= KNOB_R:
                return at, turn
        return None, None

    held = None  # (turn, degrees, next repeat time) while a knob arrow is held down
    running = True
    while running:
        step = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE)):
                running = False
            elif event.type == pygame.KEYDOWN and event.key in keys:
                turn, direction = keys[event.key]
                turn(direction * step)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                imu.calibrate()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                at, turn = knob_under(event.pos)
                if turn:  # left half of the knob turns left, right half turns right
                    degrees = step if event.pos[0] >= at[0] else -step
                    turn(degrees)
                    held = (turn, degrees, time.monotonic() + REPEAT_DELAY)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                held = None
            elif event.type == pygame.MOUSEWHEEL and event.y:
                at, turn = knob_under(pygame.mouse.get_pos())
                if turn:
                    turn(math.copysign(step, event.y))
        if held and time.monotonic() >= held[2]:
            held[0](held[1])
            held = (held[0], held[1], time.monotonic() + REPEAT_EVERY)

        imu.update()
        ai.pitch, ai.roll = imu.pitch, imu.roll
        dg.heading = imu.heading
        tc.turn_rate, tc.ball = imu.turn_rate, imu.ball

        screen.fill(BG)
        draw_readouts(screen, fonts, ai, dg, tc)
        for instrument, center in zip((ai, dg, tc), CENTERS):
            instrument.draw(screen, center)
        if imu.calibrating:
            draw_calibrating(screen, fonts, imu)
        draw_status(screen, fonts, imu, card_set_at)
        pygame.display.flip()
        clock.tick(60)

        if screenshot and not imu.calibrating and time.monotonic() - imu.cal_started > sensors.CAL_SECS + 1:
            pygame.image.save(screen, screenshot)
            running = False

    imu.close()
    pygame.quit()


if __name__ == "__main__":
    main()
