# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame-ce"]
# ///
"""Attitude indicator + directional gyro driven by the MacBook's gyro and accelerometer.

Run:  make run   (builds libimu.dylib, then: uv run compass.py)

Controls (scroll over a knob, or use the keys; Shift = 10x):
    DG PUSH knob    Left / Right    turn the card to a known heading
    DG HDG knob     [ / ]           move the heading bug
    AI adjust knob  Up / Down       move the miniature plane
    C recalibrate gyro bias, Q quit
"""

import math
import sys
import time

import pygame

import sensors
from attitude_indicator import AttitudeIndicator
from directional_gyro import DirectionalGyro
from art import BOX, CARD_R, KNOB_R

W, H = 2 * BOX + 3 * 28, 700
AI_CENTER = (28 + BOX // 2, 150 + BOX // 2)
DG_CENTER = (2 * 28 + BOX + BOX // 2, 150 + BOX // 2)

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


def draw_readouts(screen, fonts, ai, dg):
    hdg = dg.indicated
    text(screen, fonts["readout"], f"{signed(ai.pitch, 0)}° / {signed(ai.roll, 0)}°", FG, (AI_CENTER[0], 62))
    text(screen, fonts["small"], f"pitch {signed(ai.pitch, 1)}°   ·   roll {signed(ai.roll, 1)}°", DIM, (AI_CENTER[0], 112))
    text(screen, fonts["readout"], f"{round(hdg) % 360:03d}°", FG, (DG_CENTER[0], 62))
    text(screen, fonts["small"], f"{POINTS[int((hdg + 22.5) // 45) % 8]}   ·   bug {round(dg.bug) % 360:03d}°", DIM, (DG_CENTER[0], 112))


def draw_calibrating(screen, fonts, imu):
    progress = min(1.0, (time.monotonic() - imu.cal_started) / sensors.CAL_SECS)
    shade = pygame.Surface((W, H), pygame.SRCALPHA)
    for center in (AI_CENTER, DG_CENTER):
        pygame.draw.circle(shade, (0, 0, 0, 200), center, CARD_R + 4)
    screen.blit(shade, (0, 0))
    for center in (AI_CENTER, DG_CENTER):
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
        status = (f"card set {int(since // 60)}m {int(since % 60):02d}s ago   ·   "
                  f"turning {signed(imu.turn_rate, 1)}°/s   ·   IMU {imu.temp:.1f}°C")
    surf = fonts["small"].render(status, True, FG)
    rect = surf.get_rect(center=(W // 2 + 10, H - 100))
    pygame.draw.circle(screen, color, (rect.left - 18, rect.centery), 7)
    screen.blit(surf, rect)
    hints = ("Scroll over a knob, or: Left/Right card · [ ] heading bug · Up/Down plane (Shift = 10°)",
             "C recalibrate   ·   Q quit")
    for i, line in enumerate(hints):
        text(screen, fonts["hint"], line, DIM, (W // 2, H - 52 + i * 24))


def main():
    screenshot = sys.argv[sys.argv.index("--screenshot") + 1] if "--screenshot" in sys.argv else None

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Attitude + Directional Gyro")
    fonts = {"readout": pygame.font.Font(None, 84), "title": pygame.font.Font(None, 44),
             "small": pygame.font.Font(None, 26), "hint": pygame.font.Font(None, 21)}
    ai, dg = AttitudeIndicator(), DirectionalGyro()
    imu = sensors.Imu()
    card_set_at = time.monotonic()
    clock = pygame.time.Clock()

    def turn_card(degrees):
        nonlocal card_set_at
        dg.turn_card(degrees)
        card_set_at = time.monotonic()

    knobs = [((DG_CENTER, DirectionalGyro.KNOBS["card"]), turn_card),
             ((DG_CENTER, DirectionalGyro.KNOBS["bug"]), dg.turn_bug),
             ((AI_CENTER, AttitudeIndicator.KNOBS["adjust"]), ai.turn_adjust)]
    keys = {pygame.K_LEFT: (turn_card, -1), pygame.K_RIGHT: (turn_card, 1),
            pygame.K_LEFTBRACKET: (dg.turn_bug, -1), pygame.K_RIGHTBRACKET: (dg.turn_bug, 1),
            pygame.K_DOWN: (ai.turn_adjust, -1), pygame.K_UP: (ai.turn_adjust, 1)}

    running = True
    while running:
        shift = 10 if pygame.key.get_mods() & pygame.KMOD_SHIFT else 1
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key in (pygame.K_q, pygame.K_ESCAPE)):
                running = False
            elif event.type == pygame.KEYDOWN and event.key in keys:
                turn, direction = keys[event.key]
                turn(direction * shift)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_c:
                imu.calibrate()
            elif event.type == pygame.MOUSEWHEEL and event.y:
                mouse = pygame.mouse.get_pos()
                for ((cx, cy), (dx, dy)), turn in knobs:
                    if math.dist(mouse, (cx + dx, cy + dy)) <= KNOB_R:
                        turn(math.copysign(shift, event.y))

        imu.update()
        ai.pitch, ai.roll, dg.heading = imu.pitch, imu.roll, imu.heading

        screen.fill(BG)
        draw_readouts(screen, fonts, ai, dg)
        ai.draw(screen, AI_CENTER)
        dg.draw(screen, DG_CENTER)
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
