# /// script
# requires-python = ">=3.10"
# dependencies = ["pygame-ce"]
# ///
"""Draw the instrument art into assets/. The PNGs are committed; rerun this after editing.

Each part is its own layer, centred on the dial, so the instruments just rotate,
slide and stack them. Drawn at 4x and smooth-scaled down for antialiasing.

    case.png      instrument case (shared)                       392 x 392
    knob.png      knob grip with index mark, rotates when turned  66 x 66
    dg_card.png   compass card, rotates with heading              294 x 294
    dg_bug.png    heading bug at the top, rotates                 294 x 294
    dg_face.png   lubber line, plane, bezel, knob arrows          392 x 392
    ai_tape.png   sky/ground + pitch ladder, slides with pitch    294 x (294 + 180 * PX_PER_DEG)
    ai_card.png   bank card with a hole for the tape, rolls       294 x 294
    ai_face.png   miniature plane, shroud, bank pointer, bezel    392 x 392
    tc_face.png   turn coordinator dial, marks and ball tube      392 x 392
    tc_plane.png  rear-view plane, banks with turn rate           294 x 294
    tc_ball.png   inclinometer ball                               18 x 18
    tc_glass.png  ball reference lines and bezel                  392 x 392
    gm_face.png   G meter dial (-3..+3 G), bezel, reset knob      392 x 392
    gm_needle.png G meter needle with hub, rotates                294 x 294
    gm_tattle.png min/max tattletale needle, rotates              294 x 294

Run:  uv run make_assets.py
"""

import json
import math
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

OUT = Path(__file__).resolve().parent / "assets"
S = 4  # supersampling

BOX, CARD_R, BEZEL_R, KNOB_R = 392, 147, 184, 33
HOLE_R = 104          # bank card hole the pitch tape shows through
PX_PER_DEG = 2.5      # pitch tape scale
TAPE_H = 2 * CARD_R + round(180 * PX_PER_DEG)
KNOBS = {"dg_card": (-158, 158), "dg_bug": (158, 158), "ai_adjust": (-158, 158), "gm_reset": (-158, 158)}
G_RANGE, G_DEG_PER_G = 3, 45      # G meter: +/- full scale, needle degrees per G (0 G straight up)
STD_RATE_BANK = 20    # TC plane bank at standard rate (3 deg/s), where the L/R marks sit
TUBE_C, TUBE_R = (0, -120), 222   # TC ball tube: arc centre (offset from dial centre) and radius
BALL_R, BALL_MAX = 9, 16          # ball radius, and how far (deg along the arc) it can roll

WHITE = (240, 240, 236)
BLACK = (16, 16, 18)
ORANGE = (255, 122, 24)
SKY_HIGH, SKY_LOW = (36, 98, 178), (92, 168, 224)
GROUND_HIGH, GROUND_LOW = (128, 86, 54), (78, 52, 32)
CASE = (30, 31, 34)
BEZEL = (24, 24, 27)
SHROUD = (38, 38, 42)
STEM = (112, 74, 48)


# ---- drawing in 1x units on a 4x canvas

def canvas(w, h):
    return pygame.Surface((w * S, h * S), pygame.SRCALPHA)


def save(surf, name):
    w, h = surf.get_width() // S, surf.get_height() // S
    pygame.image.save(pygame.transform.smoothscale(surf, (w, h)), str(OUT / name))


def sc(p):
    return p[0] * S, p[1] * S


def line(surf, color, a, b, width):
    pygame.draw.line(surf, color, sc(a), sc(b), round(width * S))


def circle(surf, color, center, r, width=0):
    pygame.draw.circle(surf, color, sc(center), r * S, round(width * S))


def poly(surf, color, points):
    pygame.draw.polygon(surf, color, [sc(p) for p in points])


def rect(surf, color, r, radius=0):
    pygame.draw.rect(surf, color, [v * S for v in r], border_radius=radius * S)


def label(surf, text, size, color, center, angle=0):
    t = pygame.font.Font(None, size * S).render(text, True, color)
    t = pygame.transform.rotate(t, angle)
    surf.blit(t, t.get_rect(center=sc(center)))


def polar(center, r, deg):
    """Point at a compass angle (0 = up, clockwise)."""
    a = math.radians(deg)
    return center[0] + r * math.sin(a), center[1] - r * math.cos(a)


def keep_circle(surf, center, r_out, r_in=0):
    mask = canvas(surf.get_width() // S, surf.get_height() // S)
    circle(mask, (255, 255, 255, 255), center, r_out)
    if r_in:
        circle(mask, (0, 0, 0, 0), center, r_in)
    surf.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)


def gradient(surf, top, bottom, y0, y1, w):
    for y in range(y0 * S, y1 * S):
        f = (y - y0 * S) / max(1, (y1 - y0) * S - 1)
        pygame.draw.line(surf, [round(a + (b - a) * f) for a, b in zip(top, bottom)], (0, y), (w * S, y))


# ---- shared parts

C = (BOX // 2, BOX // 2)  # centre of instrument-sized layers
K = (CARD_R, CARD_R)      # centre of card-sized layers


def bezel(surf):
    circle(surf, BEZEL, C, BEZEL_R)
    circle(surf, (52, 52, 56), C, BEZEL_R, 3)       # outer highlight
    circle(surf, (0, 0, 0, 0), C, CARD_R)          # window
    circle(surf, (6, 6, 8), C, CARD_R + 4, 5)      # inner shadow


def knob():
    """Knob grip: knurled rim and an index mark. The instruments rotate it as it's turned."""
    surf = canvas(2 * KNOB_R, 2 * KNOB_R)
    at = (KNOB_R, KNOB_R)
    circle(surf, (20, 20, 22), at, KNOB_R)
    circle(surf, (48, 48, 52), at, KNOB_R - 4)
    for deg in range(0, 360, 12):
        line(surf, (70, 70, 74), polar(at, KNOB_R - 1, deg), polar(at, KNOB_R - 4, deg), 1.5)
    line(surf, WHITE, polar(at, KNOB_R - 5, 0), polar(at, KNOB_R - 13, 0), 3)
    save(surf, "knob.png")


def knob_arrows(surf, offset, text, color):
    """Fixed label and turn arrows drawn over a knob: click the left or right half to turn it."""
    x, y = C[0] + offset[0], C[1] + offset[1]
    label(surf, text, 15, color, (x, y + 7))
    for side in (-1, 1):
        tip = x + side * 25
        poly(surf, WHITE, [(tip, y), (tip - side * 8, y - 6), (tip - side * 8, y + 6)])


def static_knob(surf, offset):
    at = (C[0] + offset[0], C[1] + offset[1])
    circle(surf, (20, 20, 22), at, KNOB_R)
    circle(surf, (48, 48, 52), at, KNOB_R - 4)
    line(surf, WHITE, (at[0] - 14, at[1]), (at[0] + 14, at[1]), 3)


def case():
    surf = canvas(BOX, BOX)
    rect(surf, CASE, (0, 0, BOX, BOX), 36)
    for sx in (-1, 1):
        for sy in (-1, 1):
            circle(surf, (16, 16, 18), (C[0] + sx * 170, C[1] + sy * 170), 6)
    save(surf, "case.png")


# ---- directional gyro

def dg_card():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    circle(surf, BLACK, K, CARD_R)
    for deg in range(0, 360, 5):
        major = deg % 10 == 0
        line(surf, WHITE, polar(K, CARD_R - 3, deg), polar(K, CARD_R - (19 if major else 11), deg), 2.6 if major else 1.6)
    for deg in range(0, 360, 30):
        text = {0: "N", 90: "E", 180: "S", 270: "W"}.get(deg, str(deg // 10))
        label(surf, text, 40 if deg % 90 == 0 else 34, WHITE, polar(K, CARD_R - 42, deg), -deg)
    save(surf, "dg_card.png")


def dg_bug():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    x = CARD_R
    poly(surf, ORANGE, [(x - 15, 2), (x + 15, 2), (x + 15, 20), (x + 6, 20), (x, 11), (x - 6, 20), (x - 15, 20)])
    save(surf, "dg_bug.png")


def dg_face():
    surf = canvas(BOX, BOX)
    bezel(surf)  # first: it's a filled disc with the window cut out
    x, y = C
    # Lubber pointer: narrow at the card edge, widest low down, long sharp taper to a point above the nose
    poly(surf, WHITE, [(x - 1.5, y - CARD_R + 6), (x + 1.5, y - CARD_R + 6), (x + 7.5, y - 80), (x, y - 31), (x - 7.5, y - 80)])
    # Plane silhouette, all sharp corners: pointed nose, square wingtips, tapered fuselage
    poly(surf, WHITE, [(x, y - 27), (x + 3, y - 23), (x + 6, y - 13), (x + 6, y + 8),
                       (x + 4, y + 46), (x - 4, y + 46), (x - 6, y + 8), (x - 6, y - 13), (x - 3, y - 23)])
    poly(surf, WHITE, [(x - 52, y - 8), (x + 52, y - 8), (x + 52, y + 6), (x - 52, y + 6)])        # wings
    poly(surf, WHITE, [(x - 15, y + 33), (x + 15, y + 33), (x + 18, y + 44), (x - 18, y + 44)])    # tailplane
    line(surf, WHITE, (x, y + 76), (x, y + CARD_R - 2), 2)                                        # lubber line, bottom
    knob_arrows(surf, KNOBS["dg_card"], "HDG", WHITE)
    knob_arrows(surf, KNOBS["dg_bug"], "BUG", ORANGE)
    save(surf, "dg_face.png")


# ---- attitude indicator

def ai_tape():
    surf = canvas(2 * CARD_R, TAPE_H)
    h = TAPE_H // 2
    gradient(surf, SKY_HIGH, SKY_LOW, 0, h, 2 * CARD_R)
    gradient(surf, GROUND_HIGH, GROUND_LOW, h, TAPE_H, 2 * CARD_R)
    line(surf, WHITE, (0, h), (2 * CARD_R, h), 2.5)
    for pitch in range(5, 31, 5):
        half = 38 if pitch % 10 == 0 else 18
        for y in (h - pitch * PX_PER_DEG, h + pitch * PX_PER_DEG):
            line(surf, WHITE, (CARD_R - half, y), (CARD_R + half, y), 2)
            if pitch % 10 == 0:
                for side in (-1, 1):
                    label(surf, str(pitch), 18, WHITE, (CARD_R + side * (half + 14), y))
    save(surf, "ai_tape.png")


def ai_card():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    rect(surf, SKY_LOW, (0, 0, 2 * CARD_R, CARD_R))
    rect(surf, GROUND_HIGH, (0, CARD_R, 2 * CARD_R, CARD_R))
    line(surf, WHITE, (0, CARD_R), (2 * CARD_R, CARD_R), 3)
    for deg, length in ((10, 10), (20, 10), (30, 20), (60, 20)):
        for side in (-1, 1):
            line(surf, WHITE, polar(K, CARD_R - 3, side * deg), polar(K, CARD_R - 3 - length, side * deg), 3)
    for side in (-1, 1):  # 45 deg marks
        a, b, c = polar(K, CARD_R - 4, side * 45), polar(K, CARD_R - 14, side * 42), polar(K, CARD_R - 14, side * 48)
        poly(surf, WHITE, [a, b, c])
    poly(surf, WHITE, [(CARD_R, 6), (CARD_R - 9, 22), (CARD_R + 9, 22)])  # zero mark
    keep_circle(surf, K, CARD_R, HOLE_R)
    circle(surf, (10, 10, 12), K, HOLE_R + 2, 3)  # hole edge
    save(surf, "ai_card.png")


def ai_face():
    surf = canvas(BOX, BOX)
    bezel(surf)
    x, y = C
    # miniature plane (fixed for now): Y-shaped stem into the shroud, orange wing bars
    for side in (-1, 1):
        line(surf, STEM, (x + side * 28, y + 2), (x, y + 42), 5)
    line(surf, STEM, (x, y + 40), (x, y + 80), 7)
    rect(surf, ORANGE, (x - 96, y - 3, 68, 7))
    rect(surf, ORANGE, (x + 28, y - 3, 68, 7))
    circle(surf, ORANGE, (x, y), 5)
    shroud = canvas(BOX, BOX)
    rect(shroud, SHROUD, (0, y + 100, BOX, BOX))
    poly(shroud, SHROUD, [(x - 26, y + 66), (x + 26, y + 66), (x + 58, y + 101), (x - 58, y + 101)])
    line(shroud, (62, 62, 68), (x - 26, y + 66), (x + 26, y + 66), 2)
    keep_circle(shroud, C, CARD_R + 2)
    surf.blit(shroud, (0, 0))
    label(surf, "ATTITUDE", 16, (190, 190, 196), (x, y + 116))
    poly(surf, ORANGE, [(x - 11, y - CARD_R - 2), (x + 11, y - CARD_R - 2), (x, y - CARD_R + 20)])  # bank pointer
    static_knob(surf, KNOBS["ai_adjust"])
    save(surf, "ai_face.png")


# ---- turn coordinator

def tube_point(deg, r):
    """Point on the ball tube's arc, deg from straight down (+ = right)."""
    a = math.radians(deg)
    return C[0] + TUBE_C[0] + r * math.sin(a), C[1] + TUBE_C[1] + r * math.cos(a)


def tc_face():
    surf = canvas(BOX, BOX)
    x, y = C
    circle(surf, BLACK, C, CARD_R)
    for deg in (90, 90 + STD_RATE_BANK, 270, 270 - STD_RATE_BANK):  # wings level, and standard-rate turn
        line(surf, WHITE, polar(C, CARD_R - 4, deg), polar(C, CARD_R - 26, deg), 5)
    label(surf, "L", 30, WHITE, polar(C, CARD_R - 44, 270 - STD_RATE_BANK - 12))
    label(surf, "R", 30, WHITE, polar(C, CARD_R - 44, 90 + STD_RATE_BANK + 12))
    label(surf, "TURN COORDINATOR", 17, WHITE, (x, y - 78))
    label(surf, "2 MIN", 17, WHITE, (x, y + 58))
    span = BALL_MAX + 4
    tube = [tube_point(d / 2, TUBE_R + 12) for d in range(-2 * span, 2 * span + 1)]
    tube += [tube_point(d / 2, TUBE_R - 12) for d in range(2 * span, -2 * span - 1, -1)]
    poly(surf, (205, 205, 196), tube)
    save(surf, "tc_face.png")


def tc_plane():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    x, y = K
    poly(surf, WHITE, [(x - 95, y - 3), (x + 95, y - 3), (x + 95, y + 4), (x - 95, y + 4)])  # wings
    circle(surf, WHITE, (x, y), 11)                                                       # fuselage
    poly(surf, WHITE, [(x - 3, y - 26), (x + 3, y - 26), (x + 3, y - 8), (x - 3, y - 8)])  # fin
    poly(surf, WHITE, [(x - 22, y - 13), (x + 22, y - 13), (x + 22, y - 9), (x - 22, y - 9)])  # tailplane
    save(surf, "tc_plane.png")


def tc_ball():
    surf = canvas(2 * BALL_R, 2 * BALL_R)
    circle(surf, BLACK, (BALL_R, BALL_R), BALL_R)
    circle(surf, (80, 80, 84), (BALL_R - 3, BALL_R - 3), 2.5)  # highlight
    save(surf, "tc_ball.png")


def tc_glass():
    surf = canvas(BOX, BOX)
    bezel(surf)
    for side in (-1, 1):  # ball centred between these = coordinated
        x = C[0] + side * (BALL_R + 2)
        line(surf, BLACK, (x, tube_point(0, TUBE_R - 12)[1]), (x, tube_point(0, TUBE_R + 12)[1]), 2)
    save(surf, "tc_glass.png")


# ---- G meter

def gm_face():
    surf = canvas(BOX, BOX)
    bezel(surf)
    x, y = C
    circle(surf, BLACK, C, CARD_R)
    for tenths in range(-10 * G_RANGE, 10 * G_RANGE + 1, 5):  # a tick every 0.5 G, numbers on whole G
        g, major = tenths / 10, tenths % 10 == 0
        a = g * G_DEG_PER_G
        line(surf, WHITE, polar(C, CARD_R - 4, a), polar(C, CARD_R - (24 if major else 13), a), 3.5 if major else 2)
        if major:
            label(surf, f"{g:+.0f}" if g else "0", 34, WHITE, polar(C, CARD_R - 48, a))
    label(surf, "PUSH TO RESET", 14, (170, 170, 176), (x, y + 108))  # the axis and value are drawn above this
    static_knob(surf, KNOBS["gm_reset"])
    save(surf, "gm_face.png")


def gm_needle():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    x, y = K
    poly(surf, WHITE, [(x - 4.5, y + 20), (x + 4.5, y + 20), (x + 2.5, y - 108), (x, y - 128), (x - 2.5, y - 108)])
    circle(surf, (40, 40, 44), K, 10)
    circle(surf, (90, 90, 96), K, 10, 2)
    save(surf, "gm_needle.png")


def gm_tattle():
    surf = canvas(2 * CARD_R, 2 * CARD_R)
    x, y = K
    poly(surf, ORANGE, [(x - 3, y), (x + 3, y), (x, y - 120)])
    save(surf, "gm_tattle.png")


def main():
    pygame.init()
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.png"):
        old.unlink()
    for draw in (case, knob, dg_card, dg_bug, dg_face, ai_tape, ai_card, ai_face, tc_face, tc_plane, tc_ball, tc_glass,
                 gm_face, gm_needle, gm_tattle):
        draw()
    geometry = {"box": BOX, "card_r": CARD_R, "knob_r": KNOB_R, "knobs": KNOBS,
                "ai": {"px_per_deg": PX_PER_DEG, "horizon_row": TAPE_H // 2},
                "tc": {"std_rate_bank": STD_RATE_BANK, "tube_c": TUBE_C, "tube_r": TUBE_R, "ball_max": BALL_MAX},
                "gm": {"range": G_RANGE, "deg_per_g": G_DEG_PER_G}}
    (OUT / "assets.json").write_text(json.dumps(geometry, indent=2) + "\n")
    print(f"wrote {len(list(OUT.glob('*.png')))} layers to {OUT}")


if __name__ == "__main__":
    main()
